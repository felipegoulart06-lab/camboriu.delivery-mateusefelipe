"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from accounts import views as accounts_views
from core import views as core_views
from core.auth_views import PanelLoginView, switch_account

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", core_views.landing, name="landing"),
    path("app/", core_views.dashboard, name="dashboard"),
    path("app/configuracoes/", accounts_views.company_profile, name="company_profile"),
    path("app/configuracoes/documento/<str:field>/", accounts_views.company_own_document, name="company_own_document"),
    path("app/", include("operations.urls")),
    path("app/", include("finance.urls_company")),
    path("plataforma/", include("operations.urls_platform")),
    path("plataforma/financeiro/", include("finance.urls_platform")),
    path("motorista/", include("operations.urls_driver")),
    path("login/", PanelLoginView.as_view(), name="login"),
    path("trocar-conta/", switch_account, name="switch_account"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
