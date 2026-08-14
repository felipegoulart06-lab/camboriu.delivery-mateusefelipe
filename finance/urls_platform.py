from django.urls import path

from . import views

urlpatterns = [
    path("", views.dashboard, name="finance_dashboard"),
    path("tabela-de-precos/", views.pricing, name="finance_pricing"),
    path("entregas/<int:pk>/valores/", views.delivery_price, name="delivery_price"),
    path("faturas/", views.invoice_list, name="invoice_list"),
    path("faturas/<int:pk>/", views.invoice_detail, name="invoice_detail"),
    path("faturas/<int:pk>/boleto/", views.invoice_bank_slip, name="invoice_bank_slip"),
    path("faturas/<int:pk>/baixar/", views.invoice_pay, name="invoice_pay"),
    path("faturas/<int:pk>/cancelar/", views.invoice_cancel, name="invoice_cancel"),
    path("faturas/<int:pk>/pdf/", views.invoice_document, name="invoice_document"),
    path("empresas/<int:company_id>/faturar/", views.invoice_create, name="invoice_create"),
    path("repasses/", views.payout_list, name="payout_list"),
    path("repasses/novo/", views.payout_create, name="payout_create"),
    path("repasses/<int:pk>/", views.payout_detail, name="payout_detail"),
    path("repasses/<int:pk>/pagar/", views.payout_pay, name="payout_pay"),
    path("repasses/<int:pk>/desfazer/", views.payout_reopen, name="payout_reopen"),
    path("notificacoes/", views.notifications, name="notification_list"),
    path("notificacoes/lidas/", views.notifications_read, name="notifications_read"),
    path("solicitacoes/<int:pk>/pdf/", views.delivery_document, name="delivery_document"),
]
