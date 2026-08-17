"""Faturamento visto pela empresa contratante: fatura suas entregas e escolhe o vencimento."""
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render

from core.models import Notification
from operations.permissions import company_panel_required, company_profile_required

from . import reports
from .forms import InvoiceRequestForm
from .models import Invoice, money
from .pdf import delivery_request_pdf, invoice_pdf


def company_of(request):
    company = request.user.company
    if company is None or company.is_platform:
        raise Http404("Esta área é das empresas contratantes.")
    return company


@company_panel_required
def billing(request):
    """Extrato financeiro da empresa: entregas a faturar e faturas emitidas."""
    company = company_of(request)
    available = reports.open_deliveries_for(company)
    invoices = Invoice.objects.filter(company=company)
    receivable = invoices.filter(status__in=Invoice.RECEIVABLE_STATUSES)
    context = {
        "company": company,
        "available": available,
        "available_total": money(available.aggregate(total=Sum("price"))["total"] or 0),
        "invoices": invoices[:30],
        "open_total": money(receivable.aggregate(total=Sum("total"))["total"] or 0),
        "paid_total": money(invoices.filter(status=Invoice.Status.PAID).aggregate(total=Sum("total"))["total"] or 0),
        "overdue": [invoice for invoice in receivable if invoice.is_overdue],
        "can_invoice": company.can_invoice,
    }
    return render(request, "finance/company_billing.html", context)


@company_profile_required
def invoice_request(request):
    """A empresa com CNPJ ou MEI escolhe entregas e vencimento para gerar o boleto."""
    company = company_of(request)
    if not company.can_invoice:
        messages.error(
            request,
            "Faturamento em boleto é exclusivo de empresas com CNPJ ou MEI. Cadastros em CPF pagam por entrega via Pix.",
        )
        return redirect("company_billing")
    available = reports.open_deliveries_for(company)
    if not available.exists():
        messages.info(request, "Não há entregas concluídas aguardando faturamento.")
        return redirect("company_billing")

    form = InvoiceRequestForm(
        request.POST or None, company=company, available=available,
        suggested_due_date=reports.default_due_date(company),
    )
    if request.method == "POST" and form.is_valid():
        try:
            invoice = Invoice.create_for(
                company, form.cleaned_data["deliveries"], form.cleaned_data["due_date"],
                kind=Invoice.Kind.BANK_SLIP, user=request.user,
            )
        except ValidationError as error:
            messages.error(request, "; ".join(error.messages))
        else:
            invoice.notes = form.cleaned_data["notes"]
            invoice.save(update_fields=["notes"])
            Notification.announce(
                Notification.Kind.INVOICE_REQUEST,
                f"{company.name} faturou {invoice.deliveries.count()} entrega(s)",
                company=company,
                body=(
                    f"{company.document_label} · Fatura {invoice.number} de {invoice.total} "
                    f"com vencimento em {invoice.due_date:%d/%m/%Y}. Emita o boleto no banco."
                ),
                url=f"/plataforma/financeiro/faturas/{invoice.pk}/",
            )
            messages.success(
                request,
                f"Fatura {invoice.number} gerada. O boleto com vencimento em "
                f"{invoice.due_date:%d/%m/%Y} aparece aqui assim que a SC Transporte Executivo Delivery emitir.",
            )
            return redirect("company_invoice_detail", pk=invoice.pk)
    return render(request, "finance/company_invoice_request.html", {
        "form": form, "company": company, "available": available,
    })


@company_panel_required
def invoice_detail(request, pk):
    company = company_of(request)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    return render(request, "finance/company_invoice_detail.html", {
        "invoice": invoice,
        "deliveries": invoice.deliveries.select_related("driver").order_by("delivered_at"),
    })


@company_panel_required
def invoice_document(request, pk):
    company = company_of(request)
    invoice = get_object_or_404(Invoice, pk=pk, company=company)
    return FileResponse(invoice_pdf(invoice), content_type="application/pdf", filename=f"{invoice.number}.pdf")


@company_panel_required
def delivery_document(request, pk):
    """PDF da própria solicitação, com o cabeçalho cadastral da empresa."""
    from operations.views import tenant_queryset
    from operations.models import Delivery

    delivery = get_object_or_404(
        tenant_queryset(request, Delivery).select_related("company", "driver", "vehicle"), pk=pk,
    )
    if not delivery.is_master_confirmed:
        raise Http404("O PDF fica disponível depois que a central confirmar entregador e veículo.")
    return FileResponse(
        delivery_request_pdf(delivery, public_fleet=True), content_type="application/pdf",
        filename=f"solicitacao-{delivery.code}.pdf",
    )
