from django.urls import reverse

from operations.models import Delivery

from .alerts import inbox_for


def panel(request):
    """Dados que o menu de todos os painéis precisa."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    inbox = inbox_for(user)
    context = {
        "unread_notifications": inbox.unread().count(),
        "incoming_requests": 0,
        "live_alerts_url": reverse("live_alerts"),
    }
    if user.is_platform_staff:
        context["incoming_requests"] = Delivery.objects.filter(status=Delivery.Status.REQUESTED).count()
    return context
