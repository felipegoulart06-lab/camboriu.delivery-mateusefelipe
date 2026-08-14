import json

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from finance.models import DriverPayout, money

from .forms import DeliveryCompletionForm, PickupChecklistForm
from .models import ChecklistPhoto, Delivery, Driver, DriverPing, PickupChecklist
from .permissions import driver_required

RUNNING_STATUSES = (Delivery.Status.ACCEPTED, Delivery.Status.APPROVED, Delivery.Status.PICKUP, Delivery.Status.IN_TRANSIT)


def driver_deliveries(request):
    return Delivery.objects.filter(driver=request.driver).select_related("company", "vehicle", "pickup_checklist")


@driver_required
def home(request):
    """Mini painel do entregador: o resumo do dia e o que precisa de ação."""
    deliveries = driver_deliveries(request)
    today = timezone.localdate()
    pending = deliveries.filter(status=Delivery.Status.DISPATCHING)
    running = deliveries.filter(status__in=RUNNING_STATUSES)
    context = {
        "driver": request.driver,
        "pending": pending,
        "running": running,
        "pending_count": pending.count(),
        "running_count": running.count(),
        "delivered_today": deliveries.filter(status=Delivery.Status.DELIVERED, delivered_at__date=today).count(),
        "delivered_total": deliveries.filter(status=Delivery.Status.DELIVERED).count(),
        "checklist_pending": deliveries.filter(status=Delivery.Status.PICKUP).filter(
            Q(pickup_checklist__isnull=True) | Q(pickup_checklist__submitted_at__isnull=True),
        ).count(),
        "next_job": running.first() or pending.first(),
        "earned_month": _sum_payout(
            deliveries.filter(status=Delivery.Status.DELIVERED, delivered_at__date__gte=today.replace(day=1)),
        ),
        "pending_payout": _sum_payout(
            deliveries.filter(status=Delivery.Status.DELIVERED).exclude(payout__status=DriverPayout.Status.PAID),
        ),
        "nav": "home",
    }
    return render(request, "driver/home.html", context)


@driver_required
def jobs(request):
    deliveries = driver_deliveries(request)
    context = {
        "pending": deliveries.filter(status=Delivery.Status.DISPATCHING),
        "running": deliveries.filter(status__in=RUNNING_STATUSES),
        "nav": "jobs",
    }
    return render(request, "driver/jobs.html", context)


@driver_required
def history(request):
    deliveries = driver_deliveries(request).filter(status__in=Delivery.CLOSED_STATUSES)
    done = deliveries.filter(status=Delivery.Status.DELIVERED)
    return render(request, "driver/history.html", {
        "deliveries": deliveries[:60],
        "delivered": done.count(),
        "canceled": deliveries.filter(status=Delivery.Status.CANCELED).count(),
        "earned": _sum_payout(done),
        "transferred": _sum_payout(done.filter(payout__status=DriverPayout.Status.PAID)),
        "pending": _sum_payout(done.exclude(payout__status=DriverPayout.Status.PAID)),
        "payouts": DriverPayout.objects.filter(driver=request.driver)[:12],
        "nav": "history",
    })


def _sum_payout(queryset):
    return money(queryset.aggregate(total=Sum("driver_payout_amount"))["total"] or 0)


@driver_required
def profile(request):
    driver = request.driver
    stats = Delivery.objects.filter(driver=driver).aggregate(
        total=Count("id"), delivered=Count("id", filter=Q(status=Delivery.Status.DELIVERED)),
    )
    return render(request, "driver/profile.html", {"driver": driver, "stats": stats, "nav": "profile"})


@driver_required
@require_POST
def set_availability(request):
    """O entregador avisa a central que está disponível ou fora de operação."""
    wanted = request.POST.get("status")
    if wanted not in {Driver.Status.ACTIVE, Driver.Status.AWAY}:
        messages.error(request, "Situação inválida.")
        return redirect("driver_profile")
    request.driver.status = wanted
    request.driver.save(update_fields=["status"])
    label = "disponível" if wanted == Driver.Status.ACTIVE else "fora de operação"
    messages.success(request, f"Pronto, você está {label} para a central.")
    return redirect("driver_profile")


@driver_required
def job_detail(request, pk):
    delivery = get_object_or_404(driver_deliveries(request), pk=pk)
    checklist = getattr(delivery, "pickup_checklist", None)
    context = {
        "delivery": delivery,
        "checklist": checklist,
        "can_accept": delivery.status == Delivery.Status.DISPATCHING,
        "can_start_pickup": delivery.status in (Delivery.Status.ACCEPTED, Delivery.Status.APPROVED),
        "can_checklist": delivery.status == Delivery.Status.PICKUP and (checklist is None or not checklist.is_submitted),
        "can_complete": delivery.status == Delivery.Status.IN_TRANSIT,
        "tracking_on": delivery.is_trackable,
        "ping_seconds": settings.TRACKING_PING_SECONDS,
        "nav": "jobs",
    }
    return render(request, "driver/job_detail.html", context)


@driver_required
@require_POST
def accept_job(request, pk):
    delivery = get_object_or_404(driver_deliveries(request), pk=pk)
    if delivery.status != Delivery.Status.DISPATCHING:
        messages.error(request, "Esta corrida não está aguardando aceite.")
        return redirect("driver_job_detail", pk=pk)
    delivery.status = Delivery.Status.ACCEPTED
    delivery.save()
    delivery.register_event(f"Corrida aceita por {request.driver.name}", request.user)
    messages.success(request, "Corrida aceita. A empresa já foi avisada no painel dela.")
    return redirect("driver_job_detail", pk=pk)


@driver_required
@require_POST
def start_pickup(request, pk):
    delivery = get_object_or_404(driver_deliveries(request), pk=pk)
    if delivery.status not in (Delivery.Status.ACCEPTED, Delivery.Status.APPROVED):
        messages.error(request, "Aceite a corrida antes de sair para a coleta.")
        return redirect("driver_job_detail", pk=pk)
    delivery.status = Delivery.Status.PICKUP
    delivery.save()
    delivery.register_event("Entregador a caminho da coleta", request.user)
    messages.success(request, "Boa corrida. Mantenha o rastreio ligado até a entrega.")
    return redirect("driver_job_detail", pk=pk)


@driver_required
def checklist(request, pk):
    """Procedimento antifraude: 12 fotos obrigatórias mais a conferência do item."""
    delivery = get_object_or_404(driver_deliveries(request), pk=pk)
    existing = getattr(delivery, "pickup_checklist", None)
    if existing and existing.is_submitted:
        messages.info(request, "O checklist desta coleta já foi enviado.")
        return redirect("driver_job_detail", pk=pk)
    if delivery.status not in (Delivery.Status.PICKUP, Delivery.Status.ACCEPTED, Delivery.Status.APPROVED):
        messages.error(request, "O checklist é preenchido no momento da coleta.")
        return redirect("driver_job_detail", pk=pk)

    form = PickupChecklistForm(request.POST or None, request.FILES or None, instance=existing)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            record = form.save(commit=False)
            record.company = delivery.company
            record.delivery = delivery
            record.driver = request.driver
            record.device = request.META.get("HTTP_USER_AGENT", "")[:255]
            record.submitted_at = timezone.now()
            record.save()
            record.photos.all().delete()
            ChecklistPhoto.objects.bulk_create([
                ChecklistPhoto(checklist=record, slot=slot, image=image, lat=record.lat, lng=record.lng)
                for slot, image in form.photos()
            ])
            delivery.status = Delivery.Status.IN_TRANSIT
            delivery.save()
            delivery.register_event(
                f"Coleta conferida com checklist antifraude e {record.photos.count()} fotos", request.user,
            )
        messages.success(request, "Checklist enviado. Item liberado para transporte.")
        return redirect("driver_job_detail", pk=pk)
    return render(request, "driver/checklist_form.html", {"form": form, "delivery": delivery, "nav": "jobs"})


@driver_required
def complete_job(request, pk):
    delivery = get_object_or_404(driver_deliveries(request), pk=pk)
    if delivery.status != Delivery.Status.IN_TRANSIT:
        messages.error(request, "Conclua a coleta antes de finalizar a entrega.")
        return redirect("driver_job_detail", pk=pk)
    if not delivery.has_pickup_checklist:
        messages.error(request, "Sem checklist de coleta enviado a entrega não pode ser finalizada.")
        return redirect("driver_job_detail", pk=pk)
    form = DeliveryCompletionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        delivery.receiver = form.cleaned_data["receiver"]
        delivery.proof = form.cleaned_data["proof"]
        if form.cleaned_data["notes"]:
            delivery.notes = f"{delivery.notes}\n{form.cleaned_data['notes']}".strip()
        delivery.status = Delivery.Status.DELIVERED
        delivery.save()
        delivery.register_event(f"Entregue para {delivery.receiver}", request.user)
        messages.success(request, "Entrega concluída. Obrigado.")
        return redirect("driver_home")
    return render(request, "driver/complete_form.html", {"form": form, "delivery": delivery, "nav": "jobs"})


@driver_required
def ping(request, pk):
    """Recebe a posição do aparelho do entregador para o mapa da empresa."""
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])
    delivery = get_object_or_404(driver_deliveries(request), pk=pk)
    if not delivery.is_trackable:
        return JsonResponse({"ok": False, "reason": "corrida sem rastreio ativo"}, status=409)
    try:
        payload = json.loads(request.body or "{}")
        lat, lng = float(payload["lat"]), float(payload["lng"])
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JsonResponse({"ok": False, "reason": "coordenadas inválidas"}, status=400)
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        return JsonResponse({"ok": False, "reason": "coordenadas fora do intervalo"}, status=400)

    record = DriverPing(
        driver=request.driver, delivery=delivery, lat=lat, lng=lng,
        accuracy=_optional_float(payload.get("accuracy")),
        speed=_optional_float(payload.get("speed")),
        heading=_optional_float(payload.get("heading")),
    )
    record.save()
    request.driver.register_position(lat, lng)
    return JsonResponse({"ok": True, "recorded_at": timezone.localtime(record.recorded_at).isoformat()})


def _optional_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
