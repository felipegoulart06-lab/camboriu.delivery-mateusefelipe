from .models import Notification


def panel(request):
    """Dados que o menu de todos os painéis precisa."""
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    context = {}
    if user.is_platform_staff:
        context["unread_notifications"] = Notification.objects.unread().count()
    return context
