from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from accounts.models import Company

CENTS = Decimal("0.01")


def money(value):
    return (Decimal(value or 0)).quantize(CENTS)


class PricingPolicy(models.Model):
    """Tabela de preços da operação. O sistema mantém uma única linha, editável pelo admin master."""

    base_price = models.DecimalField("valor base da entrega", max_digits=10, decimal_places=2, default=Decimal("24.90"))
    price_per_extra_stop = models.DecimalField("valor por destino adicional", max_digits=10, decimal_places=2, default=Decimal("9.90"))
    urgent_surcharge = models.DecimalField("acréscimo urgente", max_digits=10, decimal_places=2, default=Decimal("8.00"))
    critical_surcharge = models.DecimalField("acréscimo crítico", max_digits=10, decimal_places=2, default=Decimal("18.00"))
    driver_share_percent = models.DecimalField(
        "percentual do entregador", max_digits=5, decimal_places=2, default=Decimal("70.00"),
        validators=[MinValueValidator(Decimal("0")), MaxValueValidator(Decimal("100"))],
    )
    updated_at = models.DateTimeField("atualizada em", auto_now=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "tabela de preços"
        verbose_name_plural = "tabela de preços"

    def __str__(self):
        return f"Tabela de preços · base {self.base_price}"

    @classmethod
    def current(cls):
        policy = cls.objects.order_by("pk").first()
        return policy or cls.objects.create()

    def quote(self, delivery):
        """Preço sugerido: base + destinos extras + acréscimo de prioridade."""
        from operations.models import Delivery

        extra_stops = max(delivery.destination_count - 1, 0)
        total = self.base_price + self.price_per_extra_stop * extra_stops
        if delivery.priority == Delivery.Priority.URGENT:
            total += self.urgent_surcharge
        elif delivery.priority == Delivery.Priority.CRITICAL:
            total += self.critical_surcharge
        return money(total)

    def driver_share(self, price):
        return money(Decimal(price) * self.driver_share_percent / Decimal("100"))

    def apply_to(self, delivery, save=True):
        delivery.price = self.quote(delivery)
        delivery.driver_payout_amount = self.driver_share(delivery.price)
        if save:
            delivery.save(update_fields=["price", "driver_payout_amount"])
        return delivery


class Invoice(models.Model):
    """Cobrança das entregas de uma empresa. CNPJ e MEI podem faturar em boleto."""

    class Kind(models.TextChoices):
        BANK_SLIP = "boleto", "Boleto bancário"
        RECEIPT = "recibo", "Recibo (Pix ou dinheiro)"

    class Status(models.TextChoices):
        OPEN = "open", "Aguardando emissão"
        ISSUED = "issued", "Boleto emitido"
        PAID = "paid", "Paga"
        CANCELED = "canceled", "Cancelada"

    RECEIVABLE_STATUSES = (Status.OPEN, Status.ISSUED)

    company = models.ForeignKey(Company, verbose_name="empresa", on_delete=models.PROTECT, related_name="invoices")
    number = models.CharField("número", max_length=20, unique=True, editable=False)
    kind = models.CharField("forma de cobrança", max_length=8, choices=Kind.choices, default=Kind.BANK_SLIP)
    status = models.CharField("situação", max_length=10, choices=Status.choices, default=Status.OPEN)
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)
    due_date = models.DateField("vencimento")
    issued_at = models.DateTimeField("boleto emitido em", null=True, blank=True)
    bank_slip_line = models.CharField(
        "linha digitável", max_length=60, blank=True,
        help_text="Colada do internet banking. A emissão do boleto é feita no banco.",
    )
    bank_slip_url = models.URLField("link do boleto no banco", blank=True)
    paid_at = models.DateTimeField("paga em", null=True, blank=True)
    payment_method = models.CharField("forma de pagamento", max_length=40, blank=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "fatura"
        verbose_name_plural = "faturas"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["company", "status"]), models.Index(fields=["status", "due_date"])]

    def __str__(self):
        return self.number

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = self._next_number()
        return super().save(*args, **kwargs)

    @staticmethod
    def _next_number():
        year = timezone.localdate().year
        prefix = f"FAT-{year}-"
        last = Invoice.objects.filter(number__startswith=prefix).order_by("-number").values_list("number", flat=True).first()
        sequence = int(last.rsplit("-", 1)[-1]) + 1 if last else 1
        return f"{prefix}{sequence:04d}"

    @property
    def is_receivable(self):
        return self.status in self.RECEIVABLE_STATUSES

    @property
    def is_overdue(self):
        return self.is_receivable and self.due_date < timezone.localdate()

    @property
    def days_late(self):
        return (timezone.localdate() - self.due_date).days if self.is_overdue else 0

    def recalculate(self, save=True):
        self.total = money(self.deliveries.aggregate(total=Sum("price"))["total"] or 0)
        if save:
            self.save(update_fields=["total"])
        return self.total

    def mark_paid(self, method="", when=None):
        self.status = self.Status.PAID
        self.paid_at = when or timezone.now()
        self.payment_method = method or self.payment_method
        self.save(update_fields=["status", "paid_at", "payment_method"])

    def release_deliveries(self):
        """Ao cancelar, as entregas voltam para a fila de faturamento."""
        self.deliveries.update(invoice=None)

    @classmethod
    @transaction.atomic
    def create_for(cls, company, deliveries, due_date, kind=None, user=None):
        deliveries = list(deliveries)
        if not deliveries:
            raise ValidationError("Selecione pelo menos uma entrega para faturar.")
        if any(item.company_id != company.pk for item in deliveries):
            raise ValidationError("Todas as entregas devem ser da mesma empresa.")
        if kind is None:
            kind = cls.Kind.BANK_SLIP if company.can_invoice else cls.Kind.RECEIPT
        if kind == cls.Kind.BANK_SLIP and not company.can_invoice:
            raise ValidationError("Faturamento em boleto é exclusivo de empresas com CNPJ ou MEI.")
        invoice = cls.objects.create(company=company, due_date=due_date, kind=kind, requested_by=user)
        for item in deliveries:
            item.invoice = invoice
            item.save(update_fields=["invoice"])
        invoice.recalculate()
        return invoice


class DriverPayout(models.Model):
    """Repasse de um período para o entregador."""

    class Status(models.TextChoices):
        OPEN = "open", "A pagar"
        PAID = "paid", "Pago"

    driver = models.ForeignKey("operations.Driver", verbose_name="entregador", on_delete=models.PROTECT, related_name="payouts")
    reference_start = models.DateField("período de")
    reference_end = models.DateField("período até")
    total = models.DecimalField("total", max_digits=12, decimal_places=2, default=0)
    status = models.CharField("situação", max_length=6, choices=Status.choices, default=Status.OPEN)
    method = models.CharField("forma de pagamento", max_length=40, blank=True)
    paid_at = models.DateTimeField("pago em", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField("criado em", auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = "repasse ao entregador"
        verbose_name_plural = "repasses aos entregadores"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["driver", "status"], name="repasse_por_entregador"),
            models.Index(fields=["status", "-created_at"], name="repasse_status_recentes"),
        ]

    def __str__(self):
        return f"Repasse {self.driver.name} · {self.reference_start:%d/%m} a {self.reference_end:%d/%m}"

    @property
    def rides(self):
        return self.deliveries.count()

    def recalculate(self, save=True):
        self.total = money(self.deliveries.aggregate(total=Sum("driver_payout_amount"))["total"] or 0)
        if save:
            self.save(update_fields=["total"])
        return self.total

    def mark_paid(self, method="", when=None):
        self.status = self.Status.PAID
        self.paid_at = when or timezone.now()
        self.method = method or self.method
        self.save(update_fields=["status", "paid_at", "method"])

    def release_deliveries(self):
        self.deliveries.update(payout=None)

    @classmethod
    @transaction.atomic
    def create_for(cls, driver, deliveries, start, end, user=None):
        deliveries = list(deliveries)
        if not deliveries:
            raise ValidationError("Não há entregas concluídas sem repasse neste período.")
        payout = cls.objects.create(
            driver=driver, reference_start=start, reference_end=end, created_by=user,
        )
        for item in deliveries:
            item.payout = payout
            item.save(update_fields=["payout"])
        payout.recalculate()
        return payout
