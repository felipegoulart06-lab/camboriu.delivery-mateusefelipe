from datetime import datetime, time

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.models import Company
from core.alerts import inbox_for
from core.confirm import require_confirmation
from operations.models import Delivery, Driver
from operations.permissions import master_required, platform_required

from . import reports
from .forms import BankSlipForm, DeliveryPriceForm, PaymentForm, PayoutForm, PricingPolicyForm
from .models import DriverPayout, Invoice, PricingPolicy
from .pdf import delivery_request_pdf, invoice_pdf


def _as_datetime(day):
    """Meio-dia local evita virar o dia ao converter para UTC."""
    return timezone.make_aware(datetime.combine(day, time(12, 0)))


@platform_required
def dashboard(request):
    """Painel contábil: recebimentos, repasses e desempenho por entregador e empresa."""
    context = {
        "headline": reports.headline(),
        "series": reports.monthly_series(),
        "drivers": reports.driver_metrics(),
        "companies": reports.company_metrics(),
        "policy": PricingPolicy.current(),
        "recent_invoices": Invoice.objects.select_related("company")[:8],
        "recent_payouts": DriverPayout.objects.select_related("driver")[:8],
        "overdue": Invoice.objects.filter(
            status__in=Invoice.RECEIVABLE_STATUSES, due_date__lt=timezone.localdate(),
        ).select_related("company"),
    }
    return render(request, "finance/dashboard.html", context)


@master_required
def pricing(request):
    policy = PricingPolicy.current()
    form = PricingPolicyForm(request.POST or None, instance=policy)
    if request.method == "POST" and form.is_valid():
        policy = form.save(commit=False)
        policy.updated_by = request.user
        policy.save()
        messages.success(request, "Tabela de preços atualizada. Ela vale para as próximas solicitações.")
        return redirect("finance_dashboard")
    return render(request, "finance/pricing.html", {"form": form, "policy": policy})


@platform_required
def delivery_price(request, pk):
    """Ajuste do valor cobrado e do repasse de uma entrega."""
    delivery = get_object_or_404(Delivery.objects.select_related("company", "driver"), pk=pk)
    if delivery.invoice_id:
        messages.error(request, f"Esta entrega já está na fatura {delivery.invoice.number}.")
        return redirect("dispatch_detail", pk=delivery.pk)
    form = DeliveryPriceForm(request.POST or None, instance=delivery)
    if request.method == "POST" and form.is_valid():
        form.save()
        delivery.register_event(f"Valores revisados pela administração: {delivery.price}", request.user)
        messages.success(request, "Valores da entrega atualizados.")
        return redirect("dispatch_detail", pk=delivery.pk)
    return render(request, "finance/delivery_price.html", {"form": form, "delivery": delivery})


# --- Faturas ---


@platform_required
def invoice_list(request):
    invoices = Invoice.objects.select_related("company")
    status = request.GET.get("status")
    company = request.GET.get("company")
    if status == "overdue":
        invoices = invoices.filter(status__in=Invoice.RECEIVABLE_STATUSES, due_date__lt=timezone.localdate())
    elif status:
        invoices = invoices.filter(status=status)
    if company:
        invoices = invoices.filter(company_id=company)
    return render(request, "finance/invoice_list.html", {
        "invoices": invoices,
        "statuses": Invoice.Status.choices,
        "companies": Company.objects.clients(),
        "not_billed": reports.headline()["not_billed_total"],
    })


@platform_required
def invoice_detail(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("company"), pk=pk)
    return render(request, "finance/invoice_detail.html", {
        "invoice": invoice,
        "deliveries": invoice.deliveries.select_related("driver").order_by("delivered_at"),
        "slip_form": BankSlipForm(instance=invoice),
        "payment_form": PaymentForm(),
    })


@master_required
def invoice_bank_slip(request, pk):
    """Registra a linha digitável emitida no banco e libera o boleto para a empresa."""
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status in (Invoice.Status.PAID, Invoice.Status.CANCELED):
        messages.error(request, "Esta fatura já foi encerrada.")
        return redirect("invoice_detail", pk=pk)
    form = BankSlipForm(request.POST or None, instance=invoice)
    if request.method == "POST" and form.is_valid():
        invoice = form.save(commit=False)
        if invoice.bank_slip_line or invoice.bank_slip_url:
            invoice.status = Invoice.Status.ISSUED
            invoice.issued_at = invoice.issued_at or timezone.now()
        invoice.save()
        messages.success(request, f"Boleto da fatura {invoice.number} disponível para a empresa.")
        return redirect("invoice_detail", pk=pk)
    return render(request, "finance/invoice_slip.html", {"form": form, "invoice": invoice})


@master_required
@require_POST
def invoice_pay(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if not invoice.is_receivable:
        messages.error(request, "Só é possível baixar faturas em aberto.")
        return redirect("invoice_detail", pk=pk)
    form = PaymentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Confira a data e a forma de pagamento.")
        return redirect("invoice_detail", pk=pk)
    invoice.mark_paid(form.cleaned_data["method"], _as_datetime(form.cleaned_data["paid_on"]))
    messages.success(request, f"Fatura {invoice.number} baixada como paga.")
    return redirect("invoice_detail", pk=pk)


@master_required
@require_POST
@require_confirmation("invoice_detail")
def invoice_cancel(request, pk):
    invoice = get_object_or_404(Invoice, pk=pk)
    if invoice.status == Invoice.Status.PAID:
        messages.error(request, "Fatura paga não pode ser cancelada.")
        return redirect("invoice_detail", pk=pk)
    invoice.release_deliveries()
    invoice.status = Invoice.Status.CANCELED
    invoice.notes = f"{invoice.notes}\nCancelada por {request.user.get_full_name() or request.user.username}.".strip()
    invoice.total = 0
    invoice.save(update_fields=["status", "notes", "total"])
    messages.success(request, "Fatura cancelada. As entregas voltaram para a fila de faturamento.")
    return redirect("invoice_list")


@master_required
def invoice_create(request, company_id):
    """Cobrança criada pela administração, útil para empresas que pagam por Pix."""
    company = get_object_or_404(Company.objects.clients(), pk=company_id)
    available = reports.open_deliveries_for(company)
    if request.method == "POST":
        selected = available.filter(pk__in=request.POST.getlist("deliveries"))
        try:
            invoice = Invoice.create_for(
                company, selected, reports.default_due_date(company),
                kind=Invoice.Kind.BANK_SLIP if company.can_invoice else Invoice.Kind.RECEIPT,
                user=request.user,
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, f"Fatura {invoice.number} criada com {invoice.deliveries.count()} entrega(s).")
            return redirect("invoice_detail", pk=invoice.pk)
    return render(request, "finance/invoice_create.html", {
        "company": company, "available": available, "due_date": reports.default_due_date(company),
    })


@platform_required
def invoice_document(request, pk):
    invoice = get_object_or_404(Invoice.objects.select_related("company"), pk=pk)
    return FileResponse(invoice_pdf(invoice), content_type="application/pdf", filename=f"{invoice.number}.pdf")


@platform_required
def delivery_document(request, pk):
    delivery = get_object_or_404(Delivery.objects.select_related("company", "driver", "vehicle"), pk=pk)
    return FileResponse(
        delivery_request_pdf(delivery), content_type="application/pdf",
        filename=f"solicitacao-{delivery.code}.pdf",
    )


# --- Repasses aos entregadores ---


@platform_required
def payout_list(request):
    pending = (
        Driver.objects.filter(company__is_platform=True)
        .filter(delivery__status=Delivery.Status.DELIVERED, delivery__payout__isnull=True)
        .distinct()
    )
    return render(request, "finance/payout_list.html", {
        "payouts": DriverPayout.objects.select_related("driver"),
        "pending_drivers": pending,
        "headline": reports.headline(),
        "form": PayoutForm(),
    })


@master_required
def payout_create(request):
    form = PayoutForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        driver = form.cleaned_data["driver"]
        start, end = form.cleaned_data["reference_start"], form.cleaned_data["reference_end"]
        deliveries = reports.pending_payout_deliveries(driver, start, end)
        try:
            payout = DriverPayout.create_for(driver, deliveries, start, end, request.user)
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            messages.success(request, f"Repasse de {payout.total} fechado para {driver.name}.")
            return redirect("payout_detail", pk=payout.pk)
    return render(request, "finance/payout_form.html", {"form": form})


@platform_required
def payout_detail(request, pk):
    payout = get_object_or_404(DriverPayout.objects.select_related("driver"), pk=pk)
    return render(request, "finance/payout_detail.html", {
        "payout": payout,
        "deliveries": payout.deliveries.select_related("company").order_by("delivered_at"),
        "payment_form": PaymentForm(initial={"method": "Pix"}),
    })


@master_required
@require_POST
def payout_pay(request, pk):
    payout = get_object_or_404(DriverPayout, pk=pk)
    if payout.status == DriverPayout.Status.PAID:
        messages.error(request, "Este repasse já foi pago.")
        return redirect("payout_detail", pk=pk)
    form = PaymentForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Confira a data e a forma de pagamento.")
        return redirect("payout_detail", pk=pk)
    payout.mark_paid(form.cleaned_data["method"], _as_datetime(form.cleaned_data["paid_on"]))
    messages.success(request, f"Repasse de {payout.driver.name} marcado como pago.")
    return redirect("payout_detail", pk=pk)


@master_required
@require_POST
@require_confirmation("payout_detail")
def payout_reopen(request, pk):
    payout = get_object_or_404(DriverPayout, pk=pk)
    if payout.status != DriverPayout.Status.PAID:
        payout.release_deliveries()
        payout.delete()
        messages.success(request, "Repasse desfeito. As entregas voltaram para a fila.")
        return redirect("payout_list")
    messages.error(request, "Repasse pago não pode ser desfeito.")
    return redirect("payout_detail", pk=pk)


# --- Notificações ---


@platform_required
def notifications(request):
    items = inbox_for(request.user).select_related("company")
    if request.GET.get("filtro") == "nao-lidas":
        items = items.unread()
    return render(request, "finance/notifications.html", {"notifications": items[:100]})


@platform_required
@require_POST
def notifications_read(request):
    inbox_for(request.user).mark_all_read()
    messages.success(request, "Notificações marcadas como lidas.")
    return redirect("notification_list")
