from django.urls import path

from . import platform_views as views

urlpatterns = [
    path("", views.home, name="platform_home"),
    path("despacho/", views.board, name="dispatch_board"),
    path("entregas/", views.deliveries, name="platform_deliveries"),
    path("entregas/<int:pk>/", views.dispatch_detail, name="dispatch_detail"),
    path("entregas/<int:pk>/acionar/", views.dispatch, name="dispatch_delivery"),
    path("entregas/<int:pk>/confirmar-aceite/", views.confirm_acceptance, name="dispatch_confirm"),
    path("entregas/<int:pk>/cancelar/", views.cancel_delivery, name="dispatch_cancel"),
    path("empresas/", views.company_list, name="company_list"),
    path("empresas/nova/", views.company_create, name="company_create"),
    path("empresas/<int:pk>/", views.company_detail, name="company_detail"),
    path("empresas/<int:pk>/editar/", views.company_edit, name="company_edit"),
    path("empresas/<int:pk>/situacao/", views.company_toggle, name="company_toggle"),
    path("empresas/<int:pk>/documento/<str:field>/", views.company_document, name="company_document"),
    path("empresas/<int:pk>/acessos/novo/", views.company_user_create, name="company_user_create"),
    path("empresas/<int:pk>/acessos/<int:user_id>/", views.company_user_edit, name="company_user_edit"),
    path("acessos/<int:user_id>/senha/", views.user_password, name="user_password"),
    path("equipe/", views.team, name="platform_team"),
    path("equipe/novo/", views.team_create, name="platform_team_create"),
    path("equipe/<int:user_id>/", views.team_edit, name="platform_team_edit"),
    path("entregadores/", views.drivers, name="platform_drivers"),
    path("entregadores/novo/", views.driver_create, name="platform_driver_create"),
    path("entregadores/<int:pk>/", views.driver_edit, name="platform_driver_edit"),
    path("integracao/", views.integration, name="platform_integration"),
    path("integracao/manual.pdf", views.integration_document, name="platform_integration_pdf"),
]
