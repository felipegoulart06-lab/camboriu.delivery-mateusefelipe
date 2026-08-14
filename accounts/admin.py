from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Company, User


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ("name", "document_type", "document", "city", "is_platform", "is_active", "registered_at")
    list_filter = ("is_active", "is_platform", "document_type", "tax_regime", "city")
    search_fields = ("name", "legal_name", "document", "contact_name", "city")
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        ("Identificação", {"fields": ("name", "legal_name", "slug", "document_type", "document",
                                      "state_registration", "municipal_registration", "tax_regime",
                                      "founded_on", "business_area")}),
        ("Responsável", {"fields": ("contact_name", "contact_document", "contact_role", "email", "phone")}),
        ("Endereço", {"fields": ("zip_code", "address", "complement", "district", "city", "state")}),
        ("Financeiro", {"fields": ("billing_email", "billing_phone", "invoice_due_day")}),
        ("Documentos", {"fields": Company.DOCUMENTS}),
        ("Situação", {"fields": ("registered_at", "is_active", "is_platform", "notes")}),
    )


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ("username", "email", "company", "role", "is_active")
    list_filter = ("role", "company", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("Empresa", {"fields": ("company", "role")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("Empresa", {"fields": ("company", "role", "email")}),)
