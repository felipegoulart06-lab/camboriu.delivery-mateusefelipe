"""Avisos da operação: a central e a empresa recebem caixas separadas."""
from django.urls import reverse

from .models import Notification


def inbox_for(user):
    if not user or not user.is_authenticated:
        return Notification.objects.none()
    if user.is_platform_staff:
        return Notification.objects.filter(audience=Notification.Audience.PLATFORM)
    if user.company_id and not user.is_driver:
        return Notification.objects.filter(audience=Notification.Audience.COMPANY, company_id=user.company_id)
    return Notification.objects.none()


def notify_company(delivery, title, body=""):
    return Notification.announce(
        Notification.Kind.DELIVERY_UPDATE,
        title,
        company=delivery.company,
        body=body or f"{delivery.code} · {delivery.get_item_type_display()} · {delivery.pickup_address}",
        url=reverse("delivery_detail", args=[delivery.pk]),
        audience=Notification.Audience.COMPANY,
    )
