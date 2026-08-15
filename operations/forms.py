from datetime import date

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.urls import reverse
from django.utils import timezone

from accounts.forms import PasswordFieldsMixin
from accounts.models import Company, User
from core.forms import DocumentUploadMixin, SectionedFormMixin, mark_required
from core.validators import clean_chassis, clean_cnpj, clean_cpf, clean_phone, clean_plate, clean_renavam, clean_zip_code

from .models import ChecklistPhoto, Delivery, DeliveryStop, Driver, PickupChecklist, Vehicle


class DateInput(forms.DateInput):
    input_type = "date"


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"


class CompanyModelForm(forms.ModelForm):
    def __init__(self, *args, company=None, **kwargs):
        self.company = company
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        obj = super().save(False)
        obj.company = self.company
        if commit:
            obj.save()
            self.save_m2m()
        return obj


DRIVER_SECTIONS = (
    ("Dados pessoais", "Confira os dados como estão nos documentos oficiais.",
     ("name", "cpf", "birth_date", "rg", "rg_issuer", "mother_name")),
    ("Acesso ao app", "E-mail e senha que o entregador usa no celular.",
     ("email", "password1", "password2")),
    ("Contato", "Telefone principal e alguém para acionar em caso de emergência.",
     ("phone", "emergency_contact", "emergency_phone")),
    ("Endereço", "Precisa bater com o comprovante de residência enviado.",
     ("zip_code", "address", "district", "city", "state")),
    ("Habilitação", "Para transportar carga de terceiros a CNH precisa da observação EAR.",
     ("cnh", "cnh_category", "cnh_register", "cnh_state", "cnh_issued_at",
      "cnh_first_license_at", "cnh_expires_at", "cnh_has_ear", "medical_exam_expires_at")),
    ("Vínculo e pagamento", "Como o repasse das corridas é feito.",
     ("contract_type", "status", "pix_key", "bank_name", "bank_agency", "bank_account")),
    ("Documentos", "Fotos legíveis ou PDF. Ficam anexados ao cadastro e ao contrato de prestação de serviço.",
     ("cnh_front", "cnh_back", "proof_of_address", "portrait", "criminal_record",
      "medical_certificate", "bank_proof")),
    ("Observações", "", ("notes",)),
)

DRIVER_REQUIRED = (
    "name", "cpf", "birth_date", "rg", "rg_issuer", "phone", "emergency_contact", "emergency_phone",
    "zip_code", "address", "district", "city", "state",
    "cnh", "cnh_category", "cnh_state", "cnh_issued_at", "cnh_expires_at", "medical_exam_expires_at",
    "contract_type", "status",
)

DRIVER_WIDGETS = {
    "birth_date": DateInput(), "cnh_issued_at": DateInput(), "cnh_first_license_at": DateInput(),
    "cnh_expires_at": DateInput(), "medical_exam_expires_at": DateInput(),
    "notes": forms.Textarea(attrs={"rows": 3}),
}


class DriverFieldsMixin(SectionedFormMixin, DocumentUploadMixin):
    """Regras de cadastro do entregador, iguais para a empresa e para o admin master."""

    SECTIONS = DRIVER_SECTIONS
    DOCUMENT_FIELDS = Driver.DOCUMENTS
    REQUIRED_DOCUMENTS = Driver.REQUIRED_DOCUMENTS
    MIN_AGE = 18

    def setup_driver_fields(self):
        mark_required(self, DRIVER_REQUIRED)
        self.setup_documents()
        self.fields["cpf"].widget.attrs["placeholder"] = "000.000.000-00"
        self.fields["zip_code"].widget.attrs["placeholder"] = "88330-000"
        for name in ("state", "cnh_state"):
            self.fields[name].widget.attrs["placeholder"] = "SC"
        self.fields["cnh_category"].widget.attrs["placeholder"] = "A, AB, B..."
        self.fields["pix_key"].help_text = "Informe a chave Pix ou os dados bancários completos."
        if not self.instance.pk:
            self.fields["city"].initial = "Balneário Camboriú"
            self.fields["state"].initial = "SC"

    def document_url(self, name):
        if not self.instance.pk:
            return ""
        return reverse("driver_document", args=[self.instance.pk, name])

    def clean_cpf(self):
        return clean_cpf(self.cleaned_data["cpf"])

    def clean_zip_code(self):
        return clean_zip_code(self.cleaned_data["zip_code"])

    def clean_phone(self):
        return clean_phone(self.cleaned_data["phone"])

    def clean_emergency_phone(self):
        return clean_phone(self.cleaned_data["emergency_phone"])

    def clean_cnh_category(self):
        category = self.cleaned_data["cnh_category"].strip().upper()
        if not category or set(category) - set("ABCDE"):
            raise forms.ValidationError("Categoria inválida. Use as letras A, B, C, D ou E.")
        return category

    def clean_state(self):
        return self.cleaned_data["state"].strip().upper()

    def clean_cnh_state(self):
        return self.cleaned_data["cnh_state"].strip().upper()

    def clean_birth_date(self):
        birth = self.cleaned_data["birth_date"]
        today = timezone.localdate()
        age = today.year - birth.year - ((today.month, today.day) < (birth.month, birth.day))
        if age < self.MIN_AGE:
            raise forms.ValidationError("O entregador precisa ter pelo menos 18 anos.")
        if age > 90:
            raise forms.ValidationError("Confira a data de nascimento.")
        return birth

    def clean(self):
        cleaned = super().clean()
        today = timezone.localdate()
        for name, label in (("cnh_expires_at", "A CNH"), ("medical_exam_expires_at", "O exame médico")):
            value = cleaned.get(name)
            if value and value < today:
                self.add_error(name, f"{label} está vencida. Atualize o documento antes de liberar o entregador.")
        issued, expires = cleaned.get("cnh_issued_at"), cleaned.get("cnh_expires_at")
        if issued and expires and issued >= expires:
            self.add_error("cnh_issued_at", "A emissão precisa ser anterior ao vencimento.")
        if issued and issued > today:
            self.add_error("cnh_issued_at", "A data de emissão não pode estar no futuro.")
        first = cleaned.get("cnh_first_license_at")
        if first and issued and first > issued:
            self.add_error("cnh_first_license_at", "A primeira habilitação é anterior à emissão atual.")
        if not cleaned.get("cnh_has_ear"):
            self.add_error("cnh_has_ear", "Sem a observação EAR o entregador não pode transportar carga de terceiros.")
        has_bank = all(cleaned.get(name) for name in ("bank_name", "bank_agency", "bank_account"))
        if not cleaned.get("pix_key") and not has_bank:
            self.add_error("pix_key", "Informe a chave Pix ou preencha banco, agência e conta.")
        self.validate_documents()
        return cleaned


class DriverForm(DriverFieldsMixin, CompanyModelForm):
    """Frota própria da empresa, sem login de app."""

    class Meta:
        model = Driver
        exclude = ("company", "user", "created_at", "last_lat", "last_lng", "last_position_at")
        widgets = DRIVER_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_driver_fields()


class DriverAccountForm(DriverFieldsMixin, PasswordFieldsMixin, forms.ModelForm):
    """Cadastro do entregador junto com o login que ele usa no app."""

    email = forms.EmailField(label="E-mail (login do app)")

    class Meta:
        model = Driver
        exclude = ("company", "user", "created_at", "last_lat", "last_lng", "last_position_at")
        widgets = DRIVER_WIDGETS

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company or getattr(self.instance, "company", None)
        if self.instance.pk and self.instance.user_id:
            self.fields["email"].initial = self.instance.user.email
        self.setup_driver_fields()

    @property
    def password_required(self):
        return self.instance.pk is None or self.instance.user_id is None

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicated = User.objects.filter(username=email)
        if self.instance.pk and self.instance.user_id:
            duplicated = duplicated.exclude(pk=self.instance.user_id)
        if duplicated.exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def save(self, commit=True):
        driver = super().save(False)
        driver.company = self.company
        email = self.cleaned_data["email"]
        password = self.cleaned_data.get("password1")
        parts = driver.name.split()
        user = driver.user or User(username=email)
        user.username, user.email = email, email
        user.first_name = parts[0]
        user.last_name = " ".join(parts[1:])
        user.company = self.company
        user.role = User.Role.DRIVER
        user.is_active = driver.status == Driver.Status.ACTIVE
        if password:
            user.set_password(password)
        user.save()
        driver.user = user
        if commit:
            driver.save()
        return driver


class VehicleForm(SectionedFormMixin, DocumentUploadMixin, CompanyModelForm):
    """Ficha do veículo. Cada tipo cobra os dados que fazem sentido para ele."""

    SECTIONS = (
        ("Identificação", "Dados que precisam bater com o CRLV.",
         ("kind", "plate", "plate_state", "renavam", "chassis", "brand", "model",
          "year", "model_year", "color", "fuel")),
        ("Propriedade e uso", "Quem responde pelo veículo e como ele está hoje.",
         ("owner_name", "owner_document", "mileage_km", "status", "crlv_expires_at")),
        ("Seguro e rastreamento", "Exigido para carro e utilitário que rodam com carga de terceiros.",
         ("insurer", "insurance_policy", "insurance_expires_at", "has_tracker", "tracker_provider")),
        ("Capacidade de carga", "Usado para escolher o veículo certo em cada solicitação.",
         ("capacity_kg", "top_case_liters", "doors", "body_type", "gross_weight_kg",
          "cargo_length_cm", "cargo_width_cm", "cargo_height_cm", "refrigerated", "lockable", "equipment")),
        ("Documentos e fotos", "CRLV e fotos do veículo ficam anexados ao cadastro.",
         ("crlv_document", "insurance_document", "photo_front", "photo_rear", "photo_plate", "photo_cargo")),
        ("Observações", "", ("notes",)),
    )
    DOCUMENT_FIELDS = Vehicle.DOCUMENTS
    REQUIRED_DOCUMENTS = ("crlv_document", "photo_front", "photo_plate")

    BASE_REQUIRED = (
        "kind", "plate", "plate_state", "renavam", "chassis", "brand", "model", "year", "model_year",
        "color", "fuel", "owner_name", "owner_document", "mileage_km", "crlv_expires_at", "status", "capacity_kg",
    )
    # Cada tipo tem exigências próprias, conferidas depois que o tipo é escolhido.
    BY_KIND = {
        Vehicle.Kind.MOTORCYCLE: ("top_case_liters",),
        Vehicle.Kind.CAR: ("doors", "insurer", "insurance_policy", "insurance_expires_at"),
        Vehicle.Kind.UTILITY: (
            "doors", "insurer", "insurance_policy", "insurance_expires_at", "body_type", "gross_weight_kg",
            "cargo_length_cm", "cargo_width_cm", "cargo_height_cm",
        ),
    }
    KIND_DOCUMENTS = {
        Vehicle.Kind.CAR: ("insurance_document",),
        Vehicle.Kind.UTILITY: ("insurance_document", "photo_cargo"),
    }

    class Meta:
        model = Vehicle
        exclude = ("company", "created_at")
        widgets = {
            "crlv_expires_at": DateInput(), "insurance_expires_at": DateInput(),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        mark_required(self, self.BASE_REQUIRED)
        self.setup_documents()
        self.fields["plate"].widget.attrs["placeholder"] = "ABC1D23"
        self.fields["plate_state"].widget.attrs["placeholder"] = "SC"
        self.fields["chassis"].widget.attrs["placeholder"] = "9BWZZZ377VT004251"
        self.fields["top_case_liters"].help_text = "Litragem do baú da moto."
        self.fields["gross_weight_kg"].help_text = "PBT informado no CRLV."
        for name in ("top_case_liters", "doors", "body_type", "gross_weight_kg"):
            self.fields[name].help_text = self.fields[name].help_text or "Obrigatório conforme o tipo escolhido."
        if not self.instance.pk:
            self.fields["plate_state"].initial = "SC"

    def document_url(self, name):
        if not self.instance.pk:
            return ""
        return reverse("vehicle_document", args=[self.instance.pk, name])

    def clean_plate(self):
        return clean_plate(self.cleaned_data["plate"])

    def clean_plate_state(self):
        return self.cleaned_data["plate_state"].strip().upper()

    def clean_renavam(self):
        return clean_renavam(self.cleaned_data["renavam"])

    def clean_chassis(self):
        return clean_chassis(self.cleaned_data["chassis"])

    def clean_owner_document(self):
        value = self.cleaned_data["owner_document"]
        numbers = "".join(char for char in value if char.isdigit())
        try:
            return clean_cnpj(value) if len(numbers) > 11 else clean_cpf(value)
        except ValidationError as error:
            raise forms.ValidationError(error.messages[0]) from error

    def clean_year(self):
        year = self.cleaned_data["year"]
        limit = date.today().year + 1
        if not 1980 <= year <= limit:
            raise forms.ValidationError(f"Informe um ano entre 1980 e {limit}.")
        return year

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        for name in self.BY_KIND.get(kind, ()):
            if cleaned.get(name) in (None, "", []):
                label = self.fields[name].label
                self.add_error(name, f"{label} é obrigatório para {Vehicle.Kind(kind).label.lower()}.")
        year, model_year = cleaned.get("year"), cleaned.get("model_year")
        if year and model_year and model_year < year:
            self.add_error("model_year", "O ano do modelo não pode ser menor que o de fabricação.")
        if cleaned.get("has_tracker") and not cleaned.get("tracker_provider"):
            self.add_error("tracker_provider", "Informe qual empresa faz o rastreamento.")
        if cleaned.get("body_type") == Vehicle.Body.REFRIGERATED and not cleaned.get("refrigerated"):
            self.add_error("refrigerated", "Marque a opção de compartimento refrigerado.")
        expires = cleaned.get("crlv_expires_at")
        if expires and expires < timezone.localdate():
            self.add_error("crlv_expires_at", "Licenciamento vencido. Regularize antes de usar o veículo.")
        self.validate_documents(self.REQUIRED_DOCUMENTS + self.KIND_DOCUMENTS.get(kind, ()))
        return cleaned


class DeliveryForm(CompanyModelForm):
    """Solicitação da empresa. Motorista, veículo e status ficam com a central de despacho."""

    DISPATCH_FIELDS = ("driver", "vehicle", "status", "proof", "receiver")
    COORDINATE_FIELDS = ("pickup_lat", "pickup_lng", "delivery_lat", "delivery_lng")
    COMPANY_HIDDEN = DISPATCH_FIELDS + COORDINATE_FIELDS

    class Meta:
        model = Delivery
        exclude = (
            "company", "code", "created_at", "updated_at", "dispatched_at", "accepted_at",
            "picked_up_at", "delivered_at", "price", "driver_payout_amount", "invoice", "payout",
        )
        widgets = {
            "pickup_window": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "deadline": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, company=None, dispatch=False, **kwargs):
        super().__init__(*args, company=company, **kwargs)
        if dispatch:
            fleet = Q(company=company) | Q(company__is_platform=True)
            self.fields["driver"].queryset = Driver.objects.filter(fleet)
            self.fields["vehicle"].queryset = Vehicle.objects.filter(fleet)
        else:
            for name in self.DISPATCH_FIELDS:
                self.fields.pop(name, None)
        for name in self.COORDINATE_FIELDS:
            self.fields.pop(name, None)
        self.fields["pickup_window"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["deadline"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["delivery_address"].label = "1º destino · endereço"
        self.fields["delivery_contact"].label = "1º destino · contato"


class PlatformDeliveryForm(SectionedFormMixin, forms.ModelForm):
    """Pedido de retirada aberto pela central/admin master, em nome da empresa contratante."""

    SECTIONS = (
        ("Empresa", "A solicitação entra no painel desta empresa e na fila de despacho.",
         ("company",)),
        ("Pedido", "Tudo o que a central precisa para acionar a coleta.",
         ("requester", "item_type", "priority", "declared_value", "confidential", "description")),
        ("Coleta", "Onde o entregador busca o item.",
         ("pickup_address", "pickup_contact", "pickup_window")),
        ("1º destino", "Endereço principal da entrega. Destinos extras ficam abaixo.",
         ("delivery_address", "delivery_contact", "deadline")),
        ("Observações", "Instruções da operação, acesso, sigilo ou conferência.",
         ("notes",)),
    )

    class Meta:
        model = Delivery
        fields = (
            "company", "requester", "item_type", "description", "declared_value", "confidential",
            "priority", "pickup_address", "pickup_contact", "pickup_window",
            "delivery_address", "delivery_contact", "deadline", "notes",
        )
        widgets = {
            "pickup_window": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "deadline": DateTimeInput(format="%Y-%m-%dT%H:%M"),
            "description": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["company"].queryset = Company.objects.clients().filter(
            is_active=True, registered_at__isnull=False,
        ).order_by("name")
        self.fields["company"].label = "Empresa contratante"
        self.fields["company"].help_text = "O pedido aparece para esta empresa e cai na fila do despacho."
        self.fields["delivery_address"].label = "1º destino · endereço"
        self.fields["delivery_contact"].label = "1º destino · contato"
        self.fields["pickup_window"].input_formats = ["%Y-%m-%dT%H:%M"]
        self.fields["deadline"].input_formats = ["%Y-%m-%dT%H:%M"]
        mark_required(self, (
            "company", "requester", "item_type", "description", "pickup_address",
            "pickup_contact", "delivery_address", "delivery_contact",
        ))


DeliveryStopFormSet = forms.inlineformset_factory(
    Delivery, DeliveryStop,
    fields=("address", "contact", "notes"),
    extra=3, can_delete=True, max_num=9, validate_max=True,
    labels={"address": "Endereço", "contact": "Contato", "notes": "Observações"},
)


def numbered_stops(formset, instance=None):
    """Grava os destinos extras em sequência, começando no 2 (o 1 é o endereço principal)."""
    formset.instance = instance or formset.instance
    stops = formset.save(commit=False)
    for stop in formset.deleted_objects:
        stop.delete()
    kept = [stop for stop in stops if stop.address.strip()]
    for position, stop in enumerate(kept, start=2):
        stop.order = position
        stop.delivery = formset.instance
        stop.save()
    # Renumera o que já existia para não abrir buracos na sequência.
    for position, stop in enumerate(formset.instance.stops.order_by("order", "pk"), start=2):
        if stop.order != position:
            stop.order = position
            stop.save(update_fields=["order"])
    return kept


class DispatchForm(forms.ModelForm):
    """Central de despacho aciona um entregador para a solicitação da empresa."""

    class Meta:
        model = Delivery
        fields = ("driver", "vehicle")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        fleet = Q(company=self.instance.company) | Q(company__is_platform=True)
        self.fields["driver"].queryset = Driver.objects.filter(fleet, status=Driver.Status.ACTIVE).select_related("company")
        self.fields["driver"].required = True
        self.fields["vehicle"].queryset = Vehicle.objects.filter(fleet).exclude(status=Vehicle.Status.INACTIVE)
        self.fields["vehicle"].required = True
        self.fields["driver"].label = "Entregador acionado"
        self.fields["vehicle"].label = "Veículo"

    def clean_driver(self):
        driver = self.cleaned_data["driver"]
        if driver.user_id is None:
            raise forms.ValidationError("Este entregador ainda não tem login para acompanhar a corrida no painel dele.")
        return driver


class PickupChecklistForm(forms.ModelForm):
    """As 12 fotos são obrigatórias: sem elas o entregador não conclui a coleta."""

    PHOTO_PREFIX = "photo_"

    class Meta:
        model = PickupChecklist
        fields = (
            "handover_name", "handover_document", "package_count", "seal_number",
            "identity_checked", "item_matches_request", "packaging_intact",
            "seal_applied", "documents_checked", "temperature_ok", "photos_are_original",
            "notes", "lat", "lng", "accuracy",
        )
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 3}),
            "lat": forms.HiddenInput(),
            "lng": forms.HiddenInput(),
            "accuracy": forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("lat", "lng", "accuracy"):
            self.fields[name].required = False
        for slot, label in ChecklistPhoto.Slot.choices:
            self.fields[f"{self.PHOTO_PREFIX}{slot}"] = forms.ImageField(
                label=label, required=True,
                widget=forms.ClearableFileInput(attrs={"accept": "image/*", "capture": "environment"}),
            )

    @property
    def photo_fields(self):
        return [field for field in self if field.name.startswith(self.PHOTO_PREFIX)]

    @property
    def data_fields(self):
        return [field for field in self if not field.name.startswith(self.PHOTO_PREFIX) and not field.is_hidden]

    def clean(self):
        cleaned = super().clean()
        limit = settings.CHECKLIST_MAX_PHOTO_MB * 1024 * 1024
        for field in self.fields:
            if not field.startswith(self.PHOTO_PREFIX):
                continue
            image = cleaned.get(field)
            if image and image.size > limit:
                self.add_error(field, f"Cada foto deve ter no máximo {settings.CHECKLIST_MAX_PHOTO_MB} MB.")
        return cleaned

    def photos(self):
        """Pares (etapa, arquivo) prontos para gravar."""
        return [
            (field.removeprefix(self.PHOTO_PREFIX), self.cleaned_data[field])
            for field in self.fields
            if field.startswith(self.PHOTO_PREFIX) and self.cleaned_data.get(field)
        ]


class DeliveryCompletionForm(forms.Form):
    receiver = forms.CharField(label="Quem recebeu o item", max_length=160)
    proof = forms.CharField(label="Documento ou protocolo do recebedor", max_length=255, required=False)
    notes = forms.CharField(label="Observações da entrega", widget=forms.Textarea(attrs={"rows": 3}), required=False)
