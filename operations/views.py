from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone

from core.models import Notification
from core.uploads import serve as serve_document
from finance.models import PricingPolicy

from .dossier_pdf import driver_dossier_pdf, vehicle_dossier_pdf
from .forms import DeliveryForm, DeliveryStopFormSet, DriverForm, VehicleForm, numbered_stops
from .models import ChecklistPhoto, Delivery, Driver, DriverPing, Vehicle
from .permissions import company_panel_required, master_required, platform_required, role_required

TRAIL_LIMIT = 60


def tenant_queryset(request, model):
    queryset = model.objects.all()
    if request.user.is_platform_staff:
        return queryset
    if not request.user.company_id:
        return queryset.none()
    return queryset.filter(company=request.user.company)


def fleet_queryset(request, model):
    """Frota da operação: só a equipe da plataforma consulta; o cadastro é do admin master."""
    if request.user.is_platform_staff or request.user.is_superuser:
        return model.objects.all()
    company = request.user.company
    if not company:
        return model.objects.none()
    if company.is_platform:
        return model.objects.filter(company=company)
    return model.objects.filter(company__is_platform=True)


def user_company(request, instance=None):
    if instance is not None and request.user.is_platform_staff:
        return instance.company
    if request.user.company_id:
        return request.user.company
    if instance is not None:
        return instance.company
    raise Http404("Vincule este usuário a uma empresa antes de criar registros.")


@company_panel_required
def delivery_list(request):
    deliveries = tenant_queryset(request, Delivery).select_related("driver", "vehicle", "invoice")
    status = request.GET.get("status")
    if status:
        deliveries = deliveries.filter(status=status)
    return render(request, "operations/delivery_list.html", {"deliveries": deliveries, "statuses": Delivery.Status.choices})


@company_panel_required
def delivery_detail(request, pk):
    delivery = get_object_or_404(
        tenant_queryset(request, Delivery).select_related("driver", "vehicle", "pickup_checklist", "invoice"), pk=pk,
    )
    return render(request, "operations/delivery_detail.html", {"delivery": delivery})


@role_required()
def delivery_create(request):
    if request.user.is_platform_staff:
        return redirect("platform_delivery_create")
    company = user_company(request)
    form = DeliveryForm(request.POST or None, company=company, dispatch=request.user.is_platform_staff)
    stops = DeliveryStopFormSet(request.POST or None, prefix="stops")
    if request.method == "POST" and form.is_valid() and stops.is_valid():
        with transaction.atomic():
            delivery = form.save()
            numbered_stops(stops, delivery)
            PricingPolicy.current().apply_to(delivery)
            delivery.register_event("Solicitação enviada para a central da Camboriú Delivery", request.user)
            _announce_request(delivery, request.user)
        messages.success(
            request,
            f"Solicitação {delivery.code} enviada para {delivery.destination_count} destino(s). "
            f"Valor estimado: R$ {delivery.price}. A central vai acionar um entregador.",
        )
        return redirect("delivery_detail", pk=delivery.pk)
    return render(request, "operations/delivery_form.html", {
        "form": form, "stops": stops, "title": "Nova solicitação de entrega", "cancel_url": "delivery_list",
        "policy": PricingPolicy.current(),
    })


@role_required()
def delivery_edit(request, pk):
    delivery = get_object_or_404(tenant_queryset(request, Delivery), pk=pk)
    old_status = delivery.status
    form = DeliveryForm(
        request.POST or None, instance=delivery,
        company=user_company(request, delivery), dispatch=request.user.is_platform_staff,
    )
    stops = DeliveryStopFormSet(request.POST or None, instance=delivery, prefix="stops")
    if request.method == "POST" and form.is_valid() and stops.is_valid():
        with transaction.atomic():
            delivery = form.save()
            numbered_stops(stops, delivery)
            if delivery.invoice_id is None:
                PricingPolicy.current().apply_to(delivery)
            description = "Status atualizado" if old_status != delivery.status else "Dados da entrega atualizados"
            delivery.register_event(description, request.user)
        messages.success(request, f"Entrega {delivery.code} atualizada.")
        return redirect("delivery_detail", pk=delivery.pk)
    return render(request, "operations/delivery_form.html", {
        "form": form, "stops": stops, "title": f"Editar {delivery.code}",
        "cancel_url": "delivery_detail", "cancel_pk": delivery.pk, "policy": PricingPolicy.current(),
    })


def _announce_request(delivery, user):
    """A central recebe a solicitação já com o cadastro completo de quem pediu."""
    company = delivery.company
    destinations = "; ".join(f"{stop.order}. {stop.address}" for stop in delivery.destinations)
    Notification.announce(
        Notification.Kind.DELIVERY_REQUEST,
        f"{company.name} pediu uma retirada ({delivery.code})",
        company=company,
        body=(
            f"{company.billing_name} · {company.document_label}\n"
            f"{company.full_address or 'endereço não informado'}\n"
            f"Contato: {company.contact_name or '—'} · {company.phone or '—'} · {company.email or '—'}\n"
            f"Solicitante: {delivery.requester} · {delivery.get_item_type_display()} · {delivery.get_priority_display()}\n"
            f"Coleta: {delivery.pickup_address}\n"
            f"Destinos ({delivery.destination_count}): {destinations}"
        ),
        url=reverse("dispatch_detail", args=[delivery.pk]),
    )


@company_panel_required
def delivery_tracking(request, pk):
    delivery = get_object_or_404(tenant_queryset(request, Delivery).select_related("driver"), pk=pk)
    config = {
        "dataUrl": reverse("delivery_tracking_data", args=[delivery.pk]),
        "tileUrl": settings.MAP_TILE_URL,
        "attribution": settings.MAP_TILE_ATTRIBUTION,
        "center": [settings.MAP_DEFAULT_LAT, settings.MAP_DEFAULT_LNG],
        "refreshSeconds": settings.TRACKING_PING_SECONDS,
    }
    return render(request, "operations/tracking.html", {"delivery": delivery, "config": config})


@company_panel_required
def delivery_tracking_data(request, pk):
    """Alimenta o mapa Leaflet. A posição só é publicada enquanto a corrida está ativa."""
    delivery = get_object_or_404(tenant_queryset(request, Delivery).select_related("driver"), pk=pk)
    payload = {
        "code": delivery.code,
        "status": delivery.status,
        "status_label": delivery.get_status_display(),
        "trackable": delivery.is_trackable,
        "pickup": _point(delivery.pickup_lat, delivery.pickup_lng, delivery.pickup_address),
        "destination": _point(delivery.delivery_lat, delivery.delivery_lng, delivery.delivery_address),
        "driver": None,
        "trail": [],
        "checklist_done": delivery.has_pickup_checklist,
        "updated_at": timezone.localtime(delivery.updated_at).isoformat(),
    }
    if delivery.is_trackable:
        driver = delivery.driver
        stale = True
        if driver.last_position_at:
            stale = (timezone.now() - driver.last_position_at).total_seconds() > settings.TRACKING_STALE_SECONDS
        payload["driver"] = {
            "name": driver.name,
            "phone": driver.phone,
            "vehicle": str(delivery.vehicle) if delivery.vehicle_id else None,
            "lat": driver.last_lat,
            "lng": driver.last_lng,
            "updated_at": timezone.localtime(driver.last_position_at).isoformat() if driver.last_position_at else None,
            "stale": stale,
        }
        pings = DriverPing.objects.filter(delivery=delivery).order_by("-recorded_at")[:TRAIL_LIMIT]
        payload["trail"] = [[ping.lat, ping.lng] for ping in reversed(list(pings))]
    return JsonResponse(payload)


@company_panel_required
def delivery_checklist(request, pk):
    """Termo de coleta: checklist e fotos para anexar ao contrato de prestação de serviço."""
    delivery = get_object_or_404(tenant_queryset(request, Delivery).select_related("driver", "vehicle"), pk=pk)
    checklist = getattr(delivery, "pickup_checklist", None)
    if checklist is None or not checklist.is_submitted:
        raise Http404("Esta entrega ainda não possui checklist de coleta enviado.")
    return render(request, "operations/checklist_detail.html", {"delivery": delivery, "checklist": checklist})


@company_panel_required
def checklist_photo(request, pk, photo_id):
    """As fotos são prova antifraude: só saem por aqui, com o acesso conferido."""
    delivery = get_object_or_404(tenant_queryset(request, Delivery), pk=pk)
    photo = get_object_or_404(ChecklistPhoto, pk=photo_id, checklist__delivery=delivery)
    return FileResponse(photo.image.open("rb"), filename=photo.image.name.rsplit("/", 1)[-1])


def _point(lat, lng, label):
    if lat is None or lng is None:
        return None
    return {"lat": lat, "lng": lng, "label": label}


@platform_required
def driver_list(request):
    drivers = fleet_queryset(request, Driver).select_related("company", "user")
    return render(request, "operations/driver_list.html", {
        "drivers": drivers,
        "read_only_fleet": not request.user.can_manage_resources,
    })


@master_required
def driver_create(request):
    return _resource_form(request, DriverForm, "Novo motorista", "driver_list")


@master_required
def driver_edit(request, pk):
    driver = get_object_or_404(tenant_queryset(request, Driver), pk=pk)
    return _resource_form(request, DriverForm, f"Editar {driver.name}", "driver_list", driver)


@platform_required
def vehicle_list(request):
    return render(request, "operations/vehicle_list.html", {
        "vehicles": fleet_queryset(request, Vehicle),
        "read_only_fleet": not request.user.can_manage_resources,
    })


@master_required
def vehicle_create(request):
    return _resource_form(request, VehicleForm, "Novo veículo", "vehicle_list")


@master_required
def vehicle_edit(request, pk):
    vehicle = get_object_or_404(tenant_queryset(request, Vehicle), pk=pk)
    return _resource_form(request, VehicleForm, f"Editar {vehicle.plate}", "vehicle_list", vehicle)


@platform_required
def driver_document(request, pk, field):
    """CNH, comprovante de residência e afins só saem por aqui, com o acesso conferido."""
    driver = get_object_or_404(tenant_queryset(request, Driver), pk=pk)
    return serve_document(driver, field, Driver.DOCUMENTS)


@platform_required
def vehicle_document(request, pk, field):
    vehicle = get_object_or_404(tenant_queryset(request, Vehicle), pk=pk)
    return serve_document(vehicle, field, Vehicle.DOCUMENTS)


@platform_required
def driver_dossier(request, pk):
    driver = get_object_or_404(tenant_queryset(request, Driver).select_related("user", "company"), pk=pk)
    return FileResponse(
        driver_dossier_pdf(driver),
        content_type="application/pdf",
        filename=f"dossie-entregador-{driver.pk}.pdf",
    )


@platform_required
def vehicle_dossier(request, pk):
    vehicle = get_object_or_404(tenant_queryset(request, Vehicle).select_related("company"), pk=pk)
    return FileResponse(
        vehicle_dossier_pdf(vehicle),
        content_type="application/pdf",
        filename=f"dossie-veiculo-{vehicle.plate}.pdf",
    )


def _resource_form(request, form_class, title, cancel_url, instance=None):
    form = form_class(
        request.POST or None, request.FILES or None,
        instance=instance, company=user_company(request, instance),
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Cadastro salvo. O dossiê em PDF já pode ser baixado.")
        return redirect(cancel_url)
    context = {"form": form, "title": title, "cancel_url": cancel_url}
    if instance is not None:
        context["dossier_url"] = (
            reverse("driver_dossier", args=[instance.pk])
            if form_class is DriverForm
            else reverse("vehicle_dossier", args=[instance.pk])
        )
    return render(request, "operations/form.html", context)
