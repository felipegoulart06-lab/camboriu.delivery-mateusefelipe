import hashlib
import logging
from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth import logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_POST

logger = logging.getLogger("camboriu.auth")

DEMO_PROFILES = {
    "master": {
        "label": "Admin master",
        "username": "master@camboriudelivery.local",
        "hint": "Cadastra empresas e despacha",
    },
    "empresa": {
        "label": "Empresa",
        "username": "admin@demo.local",
        "hint": "Pede retiradas e acompanha o rastreio",
    },
    "entregador": {
        "label": "Entregador",
        "username": "carlos@camboriudelivery.local",
        "hint": "Recebe as corridas no celular",
    },
}


def demo_profiles():
    """Em produção (DEMO_MODE desligado) a tela de login não sugere nenhuma conta."""
    return DEMO_PROFILES if settings.DEMO_MODE else {}


def client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded and settings.DEBUG is False and getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def attempt_keys(request, username):
    """Contadores separados por conta e por origem: uma senha errada não tranca a outra empresa."""
    digest = hashlib.sha256((username or "").strip().lower().encode()).hexdigest()[:32]
    return [f"login-fail:user:{digest}", f"login-fail:ip:{client_ip(request) or 'desconhecido'}"]


def login_is_blocked(request, username):
    limit = settings.LOGIN_ATTEMPT_LIMIT
    return any(cache.get(key, 0) >= limit for key in attempt_keys(request, username))


def register_login_failure(request, username):
    window = settings.LOGIN_ATTEMPT_WINDOW_SECONDS
    for key in attempt_keys(request, username):
        # add() só cria se não existir, então a janela conta a partir da primeira falha.
        cache.add(key, 0, window)
        try:
            cache.incr(key)
        except ValueError:  # a janela expirou entre o add e o incr
            cache.set(key, 1, window)


def clear_login_failures(request, username):
    cache.delete_many(attempt_keys(request, username))


def home_for(user):
    """Cada perfil vai para o painel certo, independente do ?next= da URL."""
    if user.is_driver:
        return reverse("driver_home")
    if user.is_platform_staff and not user.is_superuser:
        return reverse("platform_home")
    return reverse("dashboard")


class PanelAuthenticationForm(AuthenticationForm):
    """Empresa suspensa pelo admin master não entra, mesmo com a senha certa."""

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        company = user.company
        if company and not company.is_active and not user.is_superuser:
            raise ValidationError(
                "O acesso desta empresa está suspenso. Fale com a central da Camboriú Delivery.",
                code="company_inactive",
            )


@method_decorator(ensure_csrf_cookie, name="dispatch")
@method_decorator(never_cache, name="dispatch")
class PanelLoginView(LoginView):
    """Login do ERP: cookie CSRF garantido e página sem cache (evita token vencido)."""

    template_name = "registration/login.html"
    authentication_form = PanelAuthenticationForm
    # Se já estiver logado, mostramos a tela de troca em vez de redirecionar em silêncio.
    redirect_authenticated_user = False

    def get(self, request, *args, **kwargs):
        if request.user.is_authenticated and request.GET.get("trocar") != "1":
            return render(request, "registration/switch_account.html", {
                "current_home": home_for(request.user),
                "profiles": demo_profiles(),
            })
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        username = request.POST.get("username", "")
        if login_is_blocked(request, username):
            logger.warning("Login bloqueado por excesso de tentativas: %s", username[:80])
            self.object = None
            context = self.get_context_data(form=self.get_form())
            context["locked_out"] = True
            return self.render_to_response(context, status=429)
        return super().post(request, *args, **kwargs)

    def form_valid(self, form):
        clear_login_failures(self.request, form.cleaned_data.get("username", ""))
        logger.info("Login aceito: %s", form.get_user().username)
        return super().form_valid(form)

    def form_invalid(self, form):
        register_login_failure(self.request, form.data.get("username", ""))
        logger.warning("Login recusado: %s", str(form.data.get("username", ""))[:80])
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["csrf_expired"] = self.request.GET.get("expired") == "1"
        profiles = demo_profiles()
        context["profiles"] = profiles
        context["demo_mode"] = settings.DEMO_MODE
        context["attempt_limit"] = settings.LOGIN_ATTEMPT_LIMIT
        context["lock_minutes"] = max(1, settings.LOGIN_ATTEMPT_WINDOW_SECONDS // 60)
        profile = self.request.GET.get("perfil", "").strip().lower()
        context["selected_profile"] = profiles.get(profile)
        if context["selected_profile"] and not self.request.POST:
            context["form"].fields["username"].initial = context["selected_profile"]["username"]
        return context

    def get_redirect_url(self):
        """Ignora ?next= que manda empresa no painel do entregador (ou o contrário)."""
        user = self.request.user
        if not user.is_authenticated:
            return super().get_redirect_url()
        if user.is_driver or (user.is_platform_staff and not user.is_superuser):
            return home_for(user)
        next_url = super().get_redirect_url() or ""
        if next_url.startswith("/motorista") or next_url.startswith("/plataforma"):
            return reverse("dashboard")
        return next_url

    def get_success_url(self):
        return self.get_redirect_url() or home_for(self.request.user)


@require_POST
@never_cache
def switch_account(request):
    """Encerra a sessão atual e abre o login da conta escolhida."""
    perfil = (request.POST.get("perfil") or "").strip().lower()
    logout(request)
    if perfil in demo_profiles():
        return redirect(f"{reverse('login')}?{urlencode({'perfil': perfil, 'trocar': '1'})}")
    return redirect(f"{reverse('login')}?trocar=1")


def csrf_failure(request, reason=""):
    """Em vez do 403 técnico, volta ao login com aviso de token vencido."""
    next_url = request.POST.get("next") or request.GET.get("next") or ""
    params = {"expired": "1"}
    if next_url:
        params["next"] = next_url
    return redirect(f"{reverse('login')}?{urlencode(params)}")
