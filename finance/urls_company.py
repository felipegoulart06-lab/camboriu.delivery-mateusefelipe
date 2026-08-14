from django.urls import path

from . import company_views as views

urlpatterns = [
    path("financeiro/", views.billing, name="company_billing"),
    path("financeiro/faturar/", views.invoice_request, name="company_invoice_request"),
    path("financeiro/faturas/<int:pk>/", views.invoice_detail, name="company_invoice_detail"),
    path("financeiro/faturas/<int:pk>/pdf/", views.invoice_document, name="company_invoice_document"),
    path("entregas/<int:pk>/pdf/", views.delivery_document, name="company_delivery_document"),
]
