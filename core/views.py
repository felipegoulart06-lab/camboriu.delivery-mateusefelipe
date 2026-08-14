from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import redirect, render

from finance.models import Invoice, money
from operations.models import Delivery, Driver, Vehicle
from operations.permissions import registration_pending


def landing(request):
    return render(request, "landing.html")


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
    context = {
        "total": deliveries.count(),
        "in_progress": sum(by_status.get(status, 0) for status in Delivery.ACTIVE_STATUSES),
        "delivered": by_status.get(Delivery.Status.DELIVERED, 0),
        "critical": deliveries.filter(priority=Delivery.Priority.CRITICAL).exclude(status__in=Delivery.CLOSED_STATUSES).count(),
        "drivers": drivers.filter(status=Driver.Status.ACTIVE).count(),
        "vehicles": vehicles.filter(status=Vehicle.Status.AVAILABLE).count(),
        "fleet_label": fleet_label,
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
