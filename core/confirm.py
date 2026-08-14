"""Confirmação em duas etapas para cancelar, suspender ou desfazer."""
from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

CONFIRM_FIELD = "confirm"
CONFIRM_VALUE = "1"


def is_confirmed(request):
    return request.POST.get(CONFIRM_FIELD) == CONFIRM_VALUE


def require_confirmation(fallback):
    """Exige o campo confirm=1 no POST. Sem ele, a ação não executa."""

    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method == "POST" and not is_confirmed(request):
                messages.error(request, "Confirme a ação uma segunda vez para continuar.")
                return redirect(fallback, **{key: kwargs[key] for key in ("pk",) if key in kwargs})
            return view(request, *args, **kwargs)
        return wrapped
    return decorator
