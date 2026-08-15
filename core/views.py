from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from finance.models import Invoice, money
from operations.models import Delivery, Driver, Vehicle
from operations.permissions import company_panel_required, registration_pending

from .alerts import inbox_for


def landing(request):
    return render(request, "landing.html")


@login_required
def live_alerts(request):
    """Alimenta o sino e o número do menu sem recarregar a página."""
    inbox = inbox_for(request.user)
    after = 0
    try:
        after = int(request.GET.get("after") or 0)
    except (TypeError, ValueError):
        after = 0
    latest = list(inbox.filter(pk__gt=after).order_by("pk").values("id", "title", "url", "kind")[:8])
    payload = {
        "unread": inbox.unread().count(),
        "latest_id": inbox.order_by("-pk").values_list("pk", flat=True).first() or 0,
        "items": latest,
        "incoming": 0,
    }
    if request.user.is_platform_staff:
        payload["incoming"] = Delivery.objects.filter(status=Delivery.Status.REQUESTED).count()
    return JsonResponse(payload)


@login_required
def dashboard(request):
    if request.user.is_driver:
        return redirect("driver_home")
    if request.user.is_platform_staff and not request.user.is_superuser:
        return redirect("platform_home")
    if registration_pending(request):
        return redirect("company_profile")

    company = request.user.company
    if request.user.is_superuser:
        deliveries = Delivery.objects.all()
        drivers = Driver.objects.all()
        vehicles = Vehicle.objects.all()
        fleet_label = "na operação"
    elif company and company.is_platform:
        deliveries = Delivery.objects.filter(company=company)
        drivers = Driver.objects.filter(company=company)
        vehicles = Vehicle.objects.filter(company=company)
        fleet_label = "na operação"
    else:
        # Empresa cliente: pedidos dela, frota da Camboriú Delivery.
        deliveries = Delivery.objects.filter(company=company)
        drivers = Driver.objects.filter(company__is_platform=True)
        vehicles = Vehicle.objects.filter(company__is_platform=True)
        fleet_label = "frota Camboriú Delivery"

    by_status = dict(deliveries.values_list("status").annotate(total=Count("id")))
    month_start = timezone.localdate().replace(day=1)
    this_month = deliveries.filter(created_at__date__gte=month_start)
    context = {
        "total": deliveries.count(),
        "in_progress": sum(by_status.get(status, 0) for status in Delivery.ACTIVE_STATUSES),
        "delivered": by_status.get(Delivery.Status.DELIVERED, 0),
        "critical": deliveries.filter(priority=Delivery.Priority.CRITICAL).exclude(status__in=Delivery.CLOSED_STATUSES).count(),
        "drivers": drivers.filter(status=Driver.Status.ACTIVE).count(),
        "vehicles": vehicles.filter(status=Vehicle.Status.AVAILABLE).count(),
        "fleet_label": fleet_label,
        "is_client_company": bool(company and not company.is_platform and not request.user.is_superuser),
        "spent_month": money(this_month.aggregate(total=Sum("price"))["total"] or 0),
        "month_count": this_month.count(),
        "delivered_month": deliveries.filter(
            status=Delivery.Status.DELIVERED, delivered_at__date__gte=month_start,
        ).count(),
        "latest": deliveries.select_related("driver")[:8],
        "tracking": deliveries.filter(status__in=Delivery.TRACKABLE_STATUSES).select_related("driver")[:5],
        "to_invoice": money(
            deliveries.filter(status=Delivery.Status.DELIVERED, invoice__isnull=True)
            .aggregate(total=Sum("price"))["total"] or 0
        ),
        "open_invoices": money(
            Invoice.objects.filter(company=company, status__in=Invoice.RECEIVABLE_STATUSES)
            .aggregate(total=Sum("total"))["total"] or 0
        ) if company else 0,
    }
    return render(request, "dashboard.html", context)


@company_panel_required
def company_notifications(request):
    items = inbox_for(request.user).select_related("company")
    if request.GET.get("filtro") == "nao-lidas":
        items = items.unread()
    return render(request, "operations/company_notifications.html", {"notifications": items[:100]})


@company_panel_required
@require_POST
def company_notifications_read(request):
    inbox_for(request.user).mark_all_read()
    messages.success(request, "Notificações marcadas como lidas.")
    return redirect("company_notifications")
