from django.urls import path

from . import driver_views as views

urlpatterns = [
    path("", views.home, name="driver_home"),
    path("corridas/", views.jobs, name="driver_jobs"),
    path("historico/", views.history, name="driver_history"),
    path("perfil/", views.profile, name="driver_profile"),
    path("perfil/disponibilidade/", views.set_availability, name="driver_availability"),
    path("corridas/<int:pk>/", views.job_detail, name="driver_job_detail"),
    path("corridas/<int:pk>/aceitar/", views.accept_job, name="driver_accept_job"),
    path("corridas/<int:pk>/sair-para-coleta/", views.start_pickup, name="driver_start_pickup"),
    path("corridas/<int:pk>/checklist/", views.checklist, name="driver_checklist"),
    path("corridas/<int:pk>/finalizar/", views.complete_job, name="driver_complete_job"),
    path("corridas/<int:pk>/posicao/", views.ping, name="driver_ping"),
]
