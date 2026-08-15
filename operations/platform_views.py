from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.forms import CompanyForm, CompanyUserForm, PlatformUserForm, SetPasswordForm
from accounts.models import Company, User
from core.alerts import inbox_for, notify_company
from core.confirm import require_confirmation
from core.uploads import serve as serve_document
from finance import reports
from finance.models import PricingPolicy

from .dossier_pdf import company_dossier_pdf, driver_dossier_pdf
from .forms import DeliveryStopFormSet, DispatchForm, DriverAccountForm, PlatformDeliveryForm, numbered_stops
from .models import Delivery, Driver, PickupChecklist
from .permissions import master_required, platform_required
from .playbook import AUDIENCE, SECTIONS, SUBTITLE, TITLE, VERSION
from .playbook_pdf import integration_pdf


def platform_company():
    return Company.objects.platform()


@platform_required
def home(request):
    """Visão geral do admin master e da central."""
    deliveries = Delivery.objects.all()
    today = timezone.localdate()
    by_status = dict(deliveries.values_list("status").annotate(total=Count("id")))
    drivers = Driver.objects.filter(company__is_platform=True)
    context = {
        "companies_active": Company.objects.clients().filter(is_active=True).count(),
        "companies_total": Company.objects.clients().count(),
        "incoming": by_status.get(Delivery.Status.REQUESTED, 0),
        "waiting_driver": by_status.get(Delivery.Status.DISPATCHING, 0),
        "running": sum(by_status.get(status, 0) for status in Delivery.TRACKABLE_STATUSES),
        "delivered_today": deliveries.filter(status=Delivery.Status.DELIVERED, delivered_at__date=today).count(),
        "created_today": deliveries.filter(created_at__date=today).count(),
        "drivers_active": drivers.filter(status=Driver.Status.ACTIVE).count(),
        "drivers_with_login": drivers.exclude(user=None).count(),
        "checklists_today": PickupChecklist.objects.filter(submitted_at__date=today).count(),
        "critical": deliveries.filter(priority=Delivery.Priority.CRITICAL).exclude(status__in=Delivery.CLOSED_STATUSES).count(),
        "latest": deliveries.select_related("company", "driver").order_by("-created_at")[:8],
        "top_companies": Company.objects.clients().annotate(total=Count("delivery")).order_by("-total")[:5],
        "pending_registration": Company.objects.clients().filter(registered_at__isnull=True).count(),
        "finance": reports.headline(),
        "notifications": inbox_for(request.user).select_related("company")[:6],
        "unread": inbox_for(request.user).unread().count(),
    }
    return render(request, "platform/home.html", context)


@platform_required
def board(request):
    """Central de despacho: toda solicitação das empresas cai aqui primeiro."""
    deliveries = Delivery.objects.select_related("company", "driver", "vehicle")
    running = deliveries.filter(status__in=Delivery.TRACKABLE_STATUSES)
    context = {
        "incoming": deliveries.filter(status=Delivery.Status.REQUESTED),
        "waiting_driver": deliveries.filter(status=Delivery.Status.DISPATCHING),
        "running": running,
        "closed_today": deliveries.filter(status=Delivery.Status.DELIVERED, delivered_at__date=timezone.localdate()).count(),
        "available_drivers": Driver.objects.filter(status=Driver.Status.ACTIVE, company__is_platform=True).exclude(user=None),
    }
    return render(request, "platform/board.html", context)


@platform_required
def deliveries(request):
    queryset = Delivery.objects.select_related("company", "driver").order_by("-created_at")
    status = request.GET.get("status")
    company = request.GET.get("company")
    search = request.GET.get("q", "").strip()
    if status:
        queryset = queryset.filter(status=status)
    if company:
        queryset = queryset.filter(company_id=company)
    if search:
        queryset = queryset.filter(Q(code__icontains=search) | Q(requester__icontains=search) | Q(pickup_address__icontains=search))
    context = {
        "deliveries": queryset[:200],
        "statuses": Delivery.Status.choices,
        "companies": Company.objects.clients(),
    }
    return render(request, "platform/deliveries.html", context)


@platform_required
def delivery_create(request):
    """Pedido de retirada aberto pela central, já com todos os detalhes da entrega."""
    from .views import _announce_request

    form = PlatformDeliveryForm(request.POST or None)
    stops = DeliveryStopFormSet(request.POST or None, prefix="stops")
    if request.method == "POST" and form.is_valid() and stops.is_valid():
        with transaction.atomic():
            delivery = form.save()
            numbered_stops(stops, delivery)
            PricingPolicy.current().apply_to(delivery)
            delivery.register_event(
                f"Solicitação aberta pela central em nome de {delivery.company.name}",
                request.user,
            )
            _announce_request(delivery, request.user)
        messages.success(
            request,
            f"Solicitação {delivery.code} de {delivery.company.name} enviada para "
            f"{delivery.destination_count} destino(s). Valor estimado: R$ {delivery.price}.",
        )
        return redirect("dispatch_detail", pk=delivery.pk)
    return render(request, "platform/delivery_form.html", {
        "form": form, "stops": stops, "title": "Nova retirada pela central",
        "cancel_url": "dispatch_board", "policy": PricingPolicy.current(),
    })


@platform_required
def dispatch(request, pk):
    """Aciona um entregador para a solicitação e libera o contato imediato."""
    delivery = get_object_or_404(Delivery.objects.select_related("company", "driver"), pk=pk)
    if delivery.status in Delivery.CLOSED_STATUSES:
        messages.error(request, "Esta entrega já foi encerrada.")
        return redirect("dispatch_board")
    form = DispatchForm(request.POST or None, instance=delivery)
    if request.method == "POST" and form.is_valid():
        delivery = form.save(commit=False)
        delivery.status = Delivery.Status.DISPATCHING
        delivery.save()
        delivery.register_event(f"Entregador {delivery.driver.name} acionado pela central", request.user)
        notify_company(
            delivery,
            f"A central acionou um entregador para {delivery.code}",
            f"{delivery.driver.name} com o veículo {delivery.vehicle}. A central ainda precisa confirmar o pedido.",
        )
        messages.success(request, f"{delivery.driver.name} foi acionado. Confirme entregador e veículo para aceitar o pedido.")
        return redirect("dispatch_detail", pk=delivery.pk)
    return render(request, "platform/dispatch.html", {"form": form, "delivery": delivery})


@platform_required
def dispatch_detail(request, pk):
    delivery = get_object_or_404(
        Delivery.objects.select_related("company", "driver", "vehicle", "pickup_checklist"), pk=pk,
    )
    return render(request, "platform/dispatch_detail.html", {"delivery": delivery})


@platform_required
@require_POST
def confirm_acceptance(request, pk):
    """A central confirma entregador e veículo. Só então a empresa vê Pedido aceito e o PDF."""
    delivery = get_object_or_404(Delivery, pk=pk)
    if not delivery.driver_id or not delivery.vehicle_id:
        messages.error(request, "Defina o entregador e o veículo antes de confirmar o pedido.")
        return redirect("dispatch_delivery", pk=pk)
    if delivery.status in Delivery.CLOSED_STATUSES:
        messages.error(request, "Esta entrega já foi encerrada.")
        return redirect("dispatch_detail", pk=pk)
    if delivery.status == Delivery.Status.REQUESTED:
        messages.error(request, "Acione o entregador e o veículo antes de confirmar.")
        return redirect("dispatch_delivery", pk=pk)
    already = delivery.is_master_confirmed
    if delivery.status in (Delivery.Status.DISPATCHING, Delivery.Status.ACCEPTED, Delivery.Status.APPROVED):
        delivery.status = Delivery.Status.ACCEPTED
    if not delivery.master_confirmed_at:
        delivery.master_confirmed_at = timezone.now()
    delivery.save()
    if not already:
        delivery.register_event(
            f"Pedido confirmado pela central: {delivery.driver.name} · {delivery.vehicle}",
            request.user,
        )
        notify_company(
            delivery,
            f"Pedido {delivery.code} aceito pela central",
            f"Entregador {delivery.driver.name} · {delivery.vehicle.public_label}. O PDF da solicitação já está disponível.",
        )
        messages.success(request, "Pedido confirmado. A empresa já vê o aceite e pode baixar o PDF.")
    else:
        messages.info(request, "Este pedido já estava confirmado.")
    return redirect("dispatch_detail", pk=pk)


@platform_required
@require_POST
@require_confirmation("dispatch_detail")
def cancel_delivery(request, pk):
    delivery = get_object_or_404(Delivery, pk=pk)
    if delivery.status in Delivery.CLOSED_STATUSES:
        messages.error(request, "Esta entrega já foi encerrada.")
        return redirect("dispatch_detail", pk=pk)
    reason = request.POST.get("reason", "").strip()
    delivery.status = Delivery.Status.CANCELED
    delivery.save()
    delivery.register_event(f"Cancelada pela central: {reason or 'sem motivo informado'}", request.user)
    notify_company(delivery, f"A solicitação {delivery.code} foi cancelada", reason or "A central cancelou a corrida.")
    messages.success(request, "Entrega cancelada.")
    return redirect("dispatch_board")


# --- Empresas contratantes (exclusivo do admin master) ---


@master_required
def company_list(request):
    companies = Company.objects.clients().annotate(
        users_total=Count("users", distinct=True), deliveries_total=Count("delivery", distinct=True),
    )
    search = request.GET.get("q", "").strip()
    if search:
        companies = companies.filter(
            Q(name__icontains=search) | Q(legal_name__icontains=search)
            | Q(document__icontains=search) | Q(city__icontains=search)
        )
    return render(request, "platform/company_list.html", {"companies": companies, "search": search})


@master_required
def company_create(request):
    form = CompanyForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        company = form.save()
        messages.success(request, f"{company.name} cadastrada. O dossiê em PDF já pode ser baixado na ficha. Agora crie o primeiro acesso dela.")
        return redirect("company_user_create", pk=company.pk)
    return render(request, "platform/company_form.html", {"form": form, "title": "Nova empresa contratante"})


@master_required
def company_edit(request, pk):
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    form = CompanyForm(request.POST or None, request.FILES or None, instance=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Dados da empresa atualizados. O dossiê em PDF já pode ser baixado.")
        return redirect("company_detail", pk=company.pk)
    return render(request, "platform/company_form.html", {"form": form, "title": f"Editar {company.name}", "company": company})


@master_required
def company_detail(request, pk):
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    deliveries = Delivery.objects.filter(company=company)
    context = {
        "company": company,
        "users": company.users.order_by("first_name", "username"),
        "deliveries_total": deliveries.count(),
        "deliveries_open": deliveries.exclude(status__in=Delivery.CLOSED_STATUSES).count(),
        "latest": deliveries.select_related("driver").order_by("-created_at")[:8],
    }
    return render(request, "platform/company_detail.html", context)


@master_required
def company_dossier(request, pk):
    """Dossiê completo da empresa contratante, com acessos e notas internas."""
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    users = company.users.order_by("first_name", "username")
    return FileResponse(
        company_dossier_pdf(company, users=users, include_internal=True),
        content_type="application/pdf",
        filename=f"dossie-empresa-{company.slug}.pdf",
    )


@master_required
def company_document(request, pk, field):
    """Contrato social, cartão CNPJ e comprovantes anexados pela empresa."""
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    return serve_document(company, field, Company.DOCUMENTS)


@master_required
@require_POST
@require_confirmation("company_detail")
def company_toggle(request, pk):
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    company.is_active = not company.is_active
    company.save(update_fields=["is_active"])
    state = "reativada" if company.is_active else "suspensa"
    messages.success(request, f"{company.name} foi {state}.")
    return redirect("company_detail", pk=company.pk)


@master_required
def company_user_create(request, pk):
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    form = CompanyUserForm(request.POST or None, company=company)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Acesso criado para {user.email}.")
        return redirect("company_detail", pk=company.pk)
    return render(request, "platform/user_form.html", {"form": form, "title": f"Novo acesso · {company.name}", "company": company})


@master_required
def company_user_edit(request, pk, user_id):
    company = get_object_or_404(Company.objects.clients(), pk=pk)
    account = get_object_or_404(User, pk=user_id, company=company)
    form = CompanyUserForm(request.POST or None, instance=account, company=company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Acesso atualizado.")
        return redirect("company_detail", pk=company.pk)
    return render(request, "platform/user_form.html", {"form": form, "title": f"Editar {account.email or account.username}", "company": company, "account": account})


@master_required
def user_password(request, user_id):
    account = get_object_or_404(User, pk=user_id)
    form = SetPasswordForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        account.set_password(form.cleaned_data["password1"])
        account.save(update_fields=["password"])
        messages.success(request, f"Senha de {account.email or account.username} redefinida.")
        if account.company_id and not account.company.is_platform:
            return redirect("company_detail", pk=account.company_id)
        return redirect("platform_team")
    return render(request, "platform/password_form.html", {"form": form, "account": account})


# --- Equipe interna e entregadores ---


@master_required
def team(request):
    accounts = User.objects.filter(role__in=User.PLATFORM_ROLES).order_by("first_name", "username")
    return render(request, "platform/team.html", {"accounts": accounts, "superusers": User.objects.filter(is_superuser=True)})


@master_required
def team_create(request):
    form = PlatformUserForm(request.POST or None, company=platform_company())
    if request.method == "POST" and form.is_valid():
        user = form.save()
        messages.success(request, f"Acesso interno criado para {user.email}.")
        return redirect("platform_team")
    return render(request, "platform/user_form.html", {"form": form, "title": "Novo acesso interno"})


@master_required
def team_edit(request, user_id):
    account = get_object_or_404(User, pk=user_id, role__in=User.PLATFORM_ROLES)
    form = PlatformUserForm(request.POST or None, instance=account, company=account.company or platform_company())
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Acesso interno atualizado.")
        return redirect("platform_team")
    return render(request, "platform/user_form.html", {"form": form, "title": f"Editar {account.email or account.username}", "account": account})


@platform_required
def drivers(request):
    queryset = Driver.objects.filter(company__is_platform=True).select_related("user").annotate(
        rides=Count("delivery", distinct=True),
    )
    search = request.GET.get("q", "").strip()
    if search:
        queryset = queryset.filter(Q(name__icontains=search) | Q(cpf__icontains=search) | Q(phone__icontains=search))
    return render(request, "platform/driver_list.html", {"drivers": queryset, "search": search})


@master_required
def driver_create(request):
    company = platform_company()
    if company is None:
        messages.error(request, "Cadastre a transportadora da plataforma antes dos entregadores.")
        return redirect("platform_home")
    form = DriverAccountForm(request.POST or None, request.FILES or None, company=company)
    if request.method == "POST" and form.is_valid():
        driver = form.save()
        messages.success(request, f"{driver.name} cadastrado com login {driver.user.email}. O dossiê em PDF já pode ser baixado.")
        return redirect("platform_drivers")
    return render(request, "platform/driver_form.html", {"form": form, "title": "Novo entregador"})


@master_required
def driver_edit(request, pk):
    driver = get_object_or_404(Driver.objects.filter(company__is_platform=True), pk=pk)
    form = DriverAccountForm(request.POST or None, request.FILES or None, instance=driver, company=driver.company)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cadastro do entregador atualizado. O dossiê em PDF já pode ser baixado.")
        return redirect("platform_drivers")
    return render(request, "platform/driver_form.html", {"form": form, "title": f"Editar {driver.name}", "driver": driver})


@platform_required
def driver_dossier(request, pk):
    """Dossiê cadastral do entregador da frota da plataforma."""
    driver = get_object_or_404(
        Driver.objects.filter(company__is_platform=True).select_related("user", "company"),
        pk=pk,
    )
    return FileResponse(
        driver_dossier_pdf(driver),
        content_type="application/pdf",
        filename=f"dossie-entregador-{driver.pk}.pdf",
    )


@platform_required
def integration(request):
    """Manual operacional para apresentar a empresas e entregadores na integração."""
    return render(request, "platform/integration.html", {
        "title": TITLE, "subtitle": SUBTITLE, "audience": AUDIENCE,
        "version": VERSION, "sections": SECTIONS,
    })


@platform_required
def integration_document(request):
    return FileResponse(
        integration_pdf(),
        as_attachment=True,
        content_type="application/pdf",
        filename="Camboriu-Delivery-manual-de-integracao.pdf",
    )
