from django.contrib import admin

from .models import ChecklistPhoto, Delivery, DeliveryEvent, Driver, DriverPing, PickupChecklist, Vehicle


class KeepHistoryAdmin(admin.ModelAdmin):
    """Solicitações e provas da operação não saem do banco pelo admin."""

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions


@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ("name", "company", "cpf", "cnh_category", "cnh_expires_at", "status", "user", "last_position_at")
    list_filter = ("company", "status", "contract_type", "cnh_has_ear")
    search_fields = ("name", "cpf", "cnh", "rg", "city")
    readonly_fields = ("last_lat", "last_lng", "last_position_at")
    autocomplete_fields = ("user",)
    fieldsets = (
        ("Pessoais", {"fields": ("company", "user", "name", "cpf", "birth_date", "rg", "rg_issuer", "mother_name")}),
        ("Contato", {"fields": ("phone", "emergency_contact", "emergency_phone")}),
        ("Endereço", {"fields": ("zip_code", "address", "district", "city", "state")}),
        ("Habilitação", {"fields": ("cnh", "cnh_category", "cnh_register", "cnh_state", "cnh_issued_at",
                                    "cnh_first_license_at", "cnh_has_ear", "cnh_expires_at", "medical_exam_expires_at")}),
        ("Vínculo e pagamento", {"fields": ("contract_type", "status", "pix_key", "bank_name", "bank_agency", "bank_account")}),
        ("Documentos", {"fields": Driver.DOCUMENTS}),
        ("Operação", {"fields": ("last_lat", "last_lng", "last_position_at", "notes")}),
    )


@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ("plate", "model", "company", "kind", "crlv_expires_at", "status")
    list_filter = ("company", "kind", "status", "fuel", "body_type")
    search_fields = ("plate", "brand", "model", "renavam", "chassis")
    fieldsets = (
        ("Identificação", {"fields": ("company", "kind", "plate", "plate_state", "renavam", "chassis",
                                      "brand", "model", "year", "model_year", "color", "fuel")}),
        ("Propriedade e uso", {"fields": ("owner_name", "owner_document", "mileage_km", "status", "crlv_expires_at")}),
        ("Seguro e rastreamento", {"fields": ("insurer", "insurance_policy", "insurance_expires_at",
                                              "has_tracker", "tracker_provider")}),
        ("Carga", {"fields": ("capacity_kg", "top_case_liters", "doors", "body_type", "gross_weight_kg",
                              "cargo_length_cm", "cargo_width_cm", "cargo_height_cm",
                              "refrigerated", "lockable", "equipment")}),
        ("Documentos", {"fields": Vehicle.DOCUMENTS}),
        ("Observações", {"fields": ("notes",)}),
    )


class DeliveryEventInline(admin.TabularInline):
    model = DeliveryEvent
    extra = 0
    can_delete = False
    readonly_fields = ("created_at",)


@admin.register(Delivery)
class DeliveryAdmin(KeepHistoryAdmin):
    list_display = ("code", "company", "requester", "priority", "status", "driver", "created_at")
    list_filter = ("company", "status", "priority", "item_type")
    search_fields = ("code", "requester", "pickup_address", "delivery_address")
    readonly_fields = ("code", "created_at", "updated_at", "dispatched_at", "accepted_at", "picked_up_at", "delivered_at")
    inlines = [DeliveryEventInline]


@admin.register(DeliveryEvent)
class DeliveryEventAdmin(KeepHistoryAdmin):
    list_display = ("delivery", "company", "status", "created_by", "created_at")
    list_filter = ("company", "status")


@admin.register(DriverPing)
class DriverPingAdmin(admin.ModelAdmin):
    list_display = ("driver", "delivery", "lat", "lng", "recorded_at")
    list_filter = ("driver",)
    readonly_fields = ("driver", "delivery", "lat", "lng", "accuracy", "speed", "heading", "recorded_at")


class ChecklistPhotoInline(admin.TabularInline):
    model = ChecklistPhoto
    extra = 0
    can_delete = False
    readonly_fields = ("uploaded_at",)


@admin.register(PickupChecklist)
class PickupChecklistAdmin(KeepHistoryAdmin):
    list_display = ("delivery", "company", "driver", "handover_name", "submitted_at")
    list_filter = ("company",)
    search_fields = ("delivery__code", "handover_name", "handover_document", "seal_number")
    readonly_fields = ("created_at", "submitted_at", "lat", "lng", "accuracy", "device")
    inlines = [ChecklistPhotoInline]
