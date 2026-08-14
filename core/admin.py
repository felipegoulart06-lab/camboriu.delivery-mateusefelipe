from django.contrib import admin

from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "company", "created_at", "read_at")
    list_filter = ("kind", "read_at")
    search_fields = ("title", "body", "company__name")
