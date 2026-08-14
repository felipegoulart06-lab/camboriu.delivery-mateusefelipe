from django.db import models
from django.utils import timezone

from accounts.models import Company


class NotificationQuerySet(models.QuerySet):
    def unread(self):
        return self.filter(read_at__isnull=True)

    def mark_all_read(self):
        return self.unread().update(read_at=timezone.now())


class Notification(models.Model):
    """Avisos que chegam ao painel do admin master, sempre com a empresa de origem."""

    class Kind(models.TextChoices):
        DELIVERY_REQUEST = "request", "Nova solicitação de entrega"
        INVOICE_REQUEST = "invoice", "Pedido de faturamento"
        COMPANY_REGISTERED = "company", "Cadastro de empresa concluído"

    kind = models.CharField("tipo", max_length=10, choices=Kind.choices)
    company = models.ForeignKey(
        Company, verbose_name="empresa de origem", on_delete=models.CASCADE,
        related_name="notifications", null=True, blank=True,
    )
    title = models.CharField("título", max_length=180)
    body = models.TextField("detalhes", blank=True)
    url = models.CharField("link", max_length=255, blank=True)
    created_at = models.DateTimeField("recebido em", auto_now_add=True)
    read_at = models.DateTimeField("lido em", null=True, blank=True)

    objects = NotificationQuerySet.as_manager()

    class Meta:
        verbose_name = "notificação"
        verbose_name_plural = "notificações"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["read_at", "-created_at"])]

    def __str__(self):
        return self.title

    @property
    def is_unread(self):
        return self.read_at is None

    @classmethod
    def announce(cls, kind, title, company=None, body="", url=""):
        return cls.objects.create(kind=kind, title=title, company=company, body=body, url=url)
