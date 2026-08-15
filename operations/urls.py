from django.urls import path

from . import views

urlpatterns = [
    path("entregas/", views.delivery_list, name="delivery_list"),
    path("entregas/nova/", views.delivery_create, name="delivery_create"),
    path("entregas/<int:pk>/", views.delivery_detail, name="delivery_detail"),
    path("entregas/<int:pk>/editar/", views.delivery_edit, name="delivery_edit"),
    path("entregas/<int:pk>/rastreio/", views.delivery_tracking, name="delivery_tracking"),
    path("entregas/<int:pk>/rastreio/dados/", views.delivery_tracking_data, name="delivery_tracking_data"),
    path("entregas/<int:pk>/termo-de-coleta/", views.delivery_checklist, name="delivery_checklist"),
    path("entregas/<int:pk>/termo-de-coleta/foto/<int:photo_id>/", views.checklist_photo, name="checklist_photo"),
    path("motoristas/", views.driver_list, name="driver_list"),
    path("motoristas/novo/", views.driver_create, name="driver_create"),
    path("motoristas/<int:pk>/editar/", views.driver_edit, name="driver_edit"),
    path("motoristas/<int:pk>/dossie.pdf", views.driver_dossier, name="driver_dossier"),
    path("motoristas/<int:pk>/documento/<str:field>/", views.driver_document, name="driver_document"),
    path("veiculos/", views.vehicle_list, name="vehicle_list"),
    path("veiculos/novo/", views.vehicle_create, name="vehicle_create"),
    path("veiculos/<int:pk>/editar/", views.vehicle_edit, name="vehicle_edit"),
    path("veiculos/<int:pk>/dossie.pdf", views.vehicle_dossier, name="vehicle_dossier"),
    path("veiculos/<int:pk>/documento/<str:field>/", views.vehicle_document, name="vehicle_document"),
]
