"""Consultas do painel contábil: recebimentos, repasses e métricas por entregador."""
from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Case, Count, DecimalField, F, Q, Sum, Value, When
from django.db.models.functions import Coalesce, TruncMonth
from django.utils import timezone

from accounts.models import Company
from operations.models import Delivery, Driver

from .models import DriverPayout, Invoice, money

MONEY = DecimalField(max_digits=14, decimal_places=2)
ZERO = Value(Decimal("0"), output_field=MONEY)


def _sum(field, condition=None):
    """Soma em reais, já arredondada — o SQLite devolve casas demais sem o output_field."""
    expression = F(field) if condition is None else Case(When(condition, then=F(field)), default=ZERO, output_field=MONEY)
    return Coalesce(Sum(expression, output_field=MONEY), ZERO, output_field=MONEY)


def month_start(reference=None):
    today = reference or timezone.localdate()
    return today.replace(day=1)


def previous_months(count=6, reference=None):
    """Primeiro dia de cada mês, do mais antigo para o mais recente."""
    cursor = month_start(reference)
    months = [cursor]
    for _ in range(count - 1):
        cursor = (cursor - timedelta(days=1)).replace(day=1)
        months.append(cursor)
    return list(reversed(months))


def headline(reference=None):
    """Números do topo do painel: faturado, recebido, a receber e repasses."""
    today = reference or timezone.localdate()
    start = month_start(today)
    delivered = Delivery.objects.filter(status=Delivery.Status.DELIVERED)
    delivered_month = delivered.filter(delivered_at__date__gte=start)

    invoices = Invoice.objects.exclude(status=Invoice.Status.CANCELED)
    receivable = invoices.filter(status__in=Invoice.RECEIVABLE_STATUSES)
    payouts = DriverPayout.objects.all()

    revenue_month = delivered_month.aggregate(total=_sum("price"))["total"]
    payout_month = delivered_month.aggregate(total=_sum("driver_payout_amount"))["total"]
    return {
        "revenue_month": money(revenue_month),
        "payout_month": money(payout_month),
        "margin_month": money(revenue_month - payout_month),
        "rides_month": delivered_month.count(),
        "invoiced_month": money(invoices.filter(created_at__date__gte=start).aggregate(total=_sum("total"))["total"]),
        "received_month": money(invoices.filter(status=Invoice.Status.PAID, paid_at__date__gte=start).aggregate(total=_sum("total"))["total"]),
        "received_total": money(invoices.filter(status=Invoice.Status.PAID).aggregate(total=_sum("total"))["total"]),
        "receivable_total": money(receivable.aggregate(total=_sum("total"))["total"]),
        "overdue_total": money(receivable.filter(due_date__lt=today).aggregate(total=_sum("total"))["total"]),
        "overdue_count": receivable.filter(due_date__lt=today).count(),
        "payout_paid_total": money(payouts.filter(status=DriverPayout.Status.PAID).aggregate(total=_sum("total"))["total"]),
        "payout_open_total": money(payouts.filter(status=DriverPayout.Status.OPEN).aggregate(total=_sum("total"))["total"]),
        "payout_pending_total": money(
            delivered.filter(payout__isnull=True).aggregate(total=_sum("driver_payout_amount"))["total"]
        ),
        "not_billed_total": money(
            delivered.filter(invoice__isnull=True).aggregate(total=_sum("price"))["total"]
        ),
    }


def monthly_series(months=6, reference=None):
    """Receita e repasse por mês, já com a altura das barras do gráfico."""
    window = previous_months(months, reference)
    first = window[0]
    rows = (
        Delivery.objects.filter(status=Delivery.Status.DELIVERED, delivered_at__date__gte=first)
        .annotate(month=TruncMonth("delivered_at"))
        .values("month")
        .annotate(revenue=_sum("price"), payout=_sum("driver_payout_amount"), rides=Count("id"))
    )
    by_month = {row["month"].date().replace(day=1): row for row in rows if row["month"]}
    series = []
    for start in window:
        row = by_month.get(start, {})
        series.append({
            "month": start,
            "revenue": money(row.get("revenue") or 0),
            "payout": money(row.get("payout") or 0),
            "margin": money((row.get("revenue") or 0) - (row.get("payout") or 0)),
            "rides": row.get("rides") or 0,
        })
    peak = max([item["revenue"] for item in series] or [Decimal("0")]) or Decimal("1")
    for item in series:
        item["revenue_height"] = int(item["revenue"] / peak * 100)
        item["payout_height"] = int(item["payout"] / peak * 100)
    return series


def _delivered_by(group):
    """Entregas concluídas agrupadas por entregador ou por empresa.

    Cada métrica sai de uma consulta própria: somar entregas e faturas na mesma
    query multiplicaria os valores por causa dos dois joins.
    """
    rows = (
        Delivery.objects.filter(status=Delivery.Status.DELIVERED)
        .values(group)
        .annotate(
            rides=Count("id"),
            revenue=_sum("price"),
            earned=_sum("driver_payout_amount"),
            transferred=_sum("driver_payout_amount", Q(payout__status=DriverPayout.Status.PAID)),
            scheduled=_sum("driver_payout_amount", Q(payout__status=DriverPayout.Status.OPEN)),
            pending=_sum("driver_payout_amount", Q(payout__isnull=True)),
            not_billed=_sum("price", Q(invoice__isnull=True)),
        )
    )
    return {row[group]: row for row in rows}


def driver_metrics():
    """Viagens e repasses por entregador: o que já foi pago e o que ainda falta."""
    grouped = _delivered_by("driver")
    rows = [
        {
            "driver": driver,
            "name": driver.name,
            "contract": driver.get_contract_type_display(),
            "rides": grouped.get(driver.pk, {}).get("rides", 0),
            "revenue": money(grouped.get(driver.pk, {}).get("revenue")),
            "earned": money(grouped.get(driver.pk, {}).get("earned")),
            "transferred": money(grouped.get(driver.pk, {}).get("transferred")),
            "scheduled": money(grouped.get(driver.pk, {}).get("scheduled")),
            "pending": money(grouped.get(driver.pk, {}).get("pending")),
        }
        for driver in Driver.objects.filter(company__is_platform=True)
    ]
    rows.sort(key=lambda row: (-row["rides"], row["name"]))
    return rows


def company_metrics():
    """Quanto cada empresa gerou, quanto pagou e quanto está em aberto."""
    grouped = _delivered_by("company")
    invoices = {
        row["company"]: row
        for row in Invoice.objects.exclude(status=Invoice.Status.CANCELED)
        .values("company")
        .annotate(
            received=_sum("total", Q(status=Invoice.Status.PAID)),
            receivable=_sum("total", Q(status__in=Invoice.RECEIVABLE_STATUSES)),
        )
    }
    rows = [
        {
            "company": company,
            "name": company.name,
            "document_label": company.document_label,
            "can_invoice": company.can_invoice,
            "rides": grouped.get(company.pk, {}).get("rides", 0),
            "billed_total": money(grouped.get(company.pk, {}).get("revenue")),
            "not_billed": money(grouped.get(company.pk, {}).get("not_billed")),
            "received": money(invoices.get(company.pk, {}).get("received")),
            "receivable": money(invoices.get(company.pk, {}).get("receivable")),
        }
        for company in Company.objects.clients()
    ]
    rows.sort(key=lambda row: (-row["billed_total"], row["name"]))
    return rows


def open_deliveries_for(company):
    """Entregas concluídas e ainda sem fatura."""
    return (
        Delivery.objects.filter(company=company, status=Delivery.Status.DELIVERED, invoice__isnull=True)
        .exclude(price=0)
        .order_by("delivered_at")
    )


def pending_payout_deliveries(driver, start=None, end=None):
    queryset = Delivery.objects.filter(driver=driver, status=Delivery.Status.DELIVERED, payout__isnull=True)
    if start:
        queryset = queryset.filter(delivered_at__date__gte=start)
    if end:
        queryset = queryset.filter(delivered_at__date__lte=end)
    return queryset.order_by("delivered_at")


def default_due_date(company, reference=None):
    """Próxima data com o dia de vencimento preferido da empresa."""
    today = reference or timezone.localdate()
    day = min(company.invoice_due_day or 10, 28)
    candidate = today.replace(day=day)
    if candidate <= today:
        year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        candidate = date(year, month, day)
    return candidate
