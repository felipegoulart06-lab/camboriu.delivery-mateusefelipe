from django.contrib import admin

from .models import DriverPayout, Invoice, PricingPolicy


@admin.register(PricingPolicy)
class PricingPolicyAdmin(admin.ModelAdmin):
    list_display = ("base_price", "price_per_extra_stop", "driver_share_percent", "updated_at")


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("number", "company", "kind", "status", "total", "due_date", "paid_at")
    list_filter = ("status", "kind", "due_date")
    search_fields = ("number", "company__name", "company__document", "bank_slip_line")
    autocomplete_fields = ("company",)


@admin.register(DriverPayout)
class DriverPayoutAdmin(admin.ModelAdmin):
    list_display = ("driver", "reference_start", "reference_end", "total", "status", "paid_at")
    list_filter = ("status", "reference_end")
    search_fields = ("driver__name",)
