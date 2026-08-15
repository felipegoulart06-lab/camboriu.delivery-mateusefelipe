from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def registration_pending(request):
    """Empresa contratante que ainda não concluiu o próprio cadastro."""
    user = request.user
    if user.is_platform_staff or user.is_driver or not user.company_id:
        return False
    return not user.company.is_platform and not user.company.is_registered


def _registration_gate(request):
    if not registration_pending(request):
        return None
    if request.user.can_manage_company_profile:
        messages.warning(
            request,
            "Antes de usar o sistema, conclua o cadastro da sua empresa. Leva menos de dois minutos.",
        )
        return redirect("company_profile")
    messages.error(
        request,
        "O cadastro da sua empresa ainda não foi concluído. Peça ao responsável para preencher as configurações.",
    )
    return redirect("company_profile")


def role_required(resource=False):
    def decorator(view):
        @login_required
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.user.is_driver:
                return redirect("driver_home")
            gate = _registration_gate(request)
            if gate is not None:
                return gate
            allowed = request.user.can_manage_resources if resource else request.user.can_manage_deliveries
            if not allowed:
                messages.error(request, "Seu perfil possui acesso somente para consulta.")
                return redirect("dashboard")
            return view(request, *args, **kwargs)
        return wrapped
    return decorator


def company_panel_required(view):
    """Painel da empresa contratante. Entregadores usam o painel próprio."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_driver:
            return redirect("driver_home")
        gate = _registration_gate(request)
        if gate is not None:
            return gate
        return view(request, *args, **kwargs)
    return wrapped


def company_profile_required(view):
    """Cadastro e faturamento da empresa: responsáveis apenas."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if request.user.is_driver:
            return redirect("driver_home")
        if not request.user.company_id or request.user.company.is_platform:
            messages.error(request, "Esta área é do cadastro das empresas contratantes.")
            return redirect("platform_home" if request.user.is_platform_staff else "dashboard")
        if not request.user.can_manage_company_profile:
            messages.error(request, "Somente o proprietário ou o administrador da empresa mexe no cadastro.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapped


def platform_required(view):
    """Central de despacho da Camboriú Delivery."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_platform_staff:
            if request.user.is_driver:
                return redirect("driver_home")
            messages.error(request, "Área exclusiva da equipe da Camboriú Delivery.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapped


def master_required(view):
    """Admin master do sistema: cadastro de empresas e de acessos internos."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.can_manage_companies:
            if request.user.is_driver:
                return redirect("driver_home")
            if request.user.is_platform_staff:
                messages.error(request, "Somente o admin master cadastra empresas, entregadores, veículos e acessos internos.")
                return redirect("platform_home")
            messages.error(request, "Área exclusiva da administração da Camboriú Delivery.")
            return redirect("dashboard")
        return view(request, *args, **kwargs)
    return wrapped


def driver_required(view):
    """Painel do entregador: exige um cadastro de motorista vinculado ao usuário."""

    @login_required
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        driver = getattr(request.user, "driver_profile", None)
        if driver is None:
            messages.error(request, "Este login não é de entregador. Entre com a conta do app do entregador.")
            if request.user.is_platform_staff:
                return redirect("platform_home")
            return redirect("dashboard")
        request.driver = driver
        return view(request, *args, **kwargs)
    return wrapped
