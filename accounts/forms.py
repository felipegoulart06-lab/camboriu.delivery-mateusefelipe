from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify

from core.forms import DateInput, DocumentUploadMixin, SectionedFormMixin, mark_required
from core.validators import clean_cnpj, clean_cpf, clean_phone, clean_zip_code

from .models import Company, User


def unique_slug(name, instance=None):
    base = slugify(name)[:40] or "empresa"
    slug, index = base, 2
    queryset = Company.objects.all()
    if instance and instance.pk:
        queryset = queryset.exclude(pk=instance.pk)
    while queryset.filter(slug=slug).exists():
        slug = f"{base}-{index}"
        index += 1
    return slug


IDENTITY_FIELDS = (
    "name", "legal_name", "document_type", "document", "state_registration",
    "municipal_registration", "tax_regime", "founded_on", "business_area",
)
CONTACT_FIELDS = ("contact_name", "contact_document", "contact_role", "email", "phone")
ADDRESS_FIELDS = ("zip_code", "address", "complement", "district", "city", "state")
BILLING_FIELDS = ("billing_email", "billing_phone", "invoice_due_day")
COMPANY_DOCUMENTS = Company.DOCUMENTS

REGISTRATION_FIELDS = IDENTITY_FIELDS + CONTACT_FIELDS + ADDRESS_FIELDS + BILLING_FIELDS

COMPANY_SECTIONS = (
    ("Identificação", "Dados como constam no cartão CNPJ ou no seu documento pessoal.", IDENTITY_FIELDS),
    ("Responsável", "Quem responde pela empresa dentro da plataforma.", CONTACT_FIELDS),
    ("Endereço de coleta e cobrança", "Endereço oficial da empresa.", ADDRESS_FIELDS),
    ("Financeiro", "Para onde enviamos o boleto e em que dia ele vence.", BILLING_FIELDS),
    ("Documentos", "Fotos legíveis ou PDF. Necessários para liberar o faturamento.", COMPANY_DOCUMENTS),
    ("Interno", "", ("is_active", "notes")),
)

COMPANY_WIDGETS = {
    "notes": forms.Textarea(attrs={"rows": 3}),
    "founded_on": DateInput(),
}


class CompanyFieldsMixin(SectionedFormMixin, DocumentUploadMixin):
    """Validações do cadastro da empresa, compartilhadas pelo admin master e pela própria empresa."""

    SECTIONS = COMPANY_SECTIONS
    DOCUMENT_FIELDS = COMPANY_DOCUMENTS
    BASE_REQUIRED = (
        "name", "legal_name", "document_type", "document", "tax_regime", "business_area",
        "contact_name", "contact_document", "email", "phone",
        "zip_code", "address", "district", "city", "state", "invoice_due_day",
    )

    def setup_company_fields(self):
        mark_required(self, self.BASE_REQUIRED)
        self.setup_documents()
        self.fields["document"].widget.attrs["placeholder"] = "00.000.000/0001-00"
        self.fields["contact_document"].widget.attrs["placeholder"] = "000.000.000-00"
        self.fields["zip_code"].widget.attrs["placeholder"] = "88330-000"
        self.fields["state"].widget.attrs["placeholder"] = "SC"
        self.fields["state_registration"].help_text = "Escreva ISENTO se a empresa não tiver."
        if not self.instance.pk:
            self.fields["city"].initial = "Balneário Camboriú"
            self.fields["state"].initial = "SC"

    @property
    def document_type_chosen(self):
        return self.data.get("document_type") or self.initial.get("document_type") or self.instance.document_type

    def clean_document(self):
        value = self.cleaned_data["document"]
        checker = clean_cpf if self.document_type_chosen == Company.DocumentType.CPF else clean_cnpj
        try:
            return checker(value)
        except ValidationError as error:
            raise forms.ValidationError(error.messages[0]) from error

    def clean_contact_document(self):
        try:
            return clean_cpf(self.cleaned_data["contact_document"])
        except ValidationError as error:
            raise forms.ValidationError(error.messages[0]) from error

    def clean_zip_code(self):
        return clean_zip_code(self.cleaned_data["zip_code"])

    def clean_phone(self):
        return clean_phone(self.cleaned_data["phone"])

    def clean_state(self):
        return self.cleaned_data["state"].strip().upper()

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("document_type")
        if kind in Company.INVOICEABLE_DOCUMENTS and not cleaned.get("state_registration"):
            self.add_error("state_registration", "Informe a inscrição estadual ou escreva ISENTO.")
        founded = cleaned.get("founded_on")
        if founded and founded > timezone.localdate():
            self.add_error("founded_on", "A data de abertura não pode estar no futuro.")
        return cleaned


class CompanyForm(CompanyFieldsMixin, forms.ModelForm):
    """Cadastro de empresa contratante feito pelo admin master.

    Os anexos ficam opcionais aqui: a própria empresa envia os documentos ao concluir o cadastro dela.
    """

    class Meta:
        model = Company
        fields = REGISTRATION_FIELDS + COMPANY_DOCUMENTS + ("is_active", "notes")
        widgets = COMPANY_WIDGETS

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_company_fields()

    def document_url(self, name):
        if not self.instance.pk:
            return ""
        return reverse("company_document", args=[self.instance.pk, name])

    def save(self, commit=True):
        company = super().save(False)
        company.slug = unique_slug(company.name, company)
        if commit:
            company.save()
        return company


class CompanyProfileForm(CompanyFieldsMixin, forms.ModelForm):
    """Cadastro que a própria empresa preenche antes de usar o sistema."""

    class Meta:
        model = Company
        fields = REGISTRATION_FIELDS + COMPANY_DOCUMENTS
        widgets = COMPANY_WIDGETS
        help_texts = {
            "name": "Como sua empresa é conhecida pelos clientes.",
            "legal_name": "Razão social do CNPJ ou seu nome completo, se você usa CPF.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setup_company_fields()
        mark_required(self, ("founded_on", "billing_email", "contact_role"))

    def document_url(self, name):
        return reverse("company_own_document", args=[name])

    @property
    def required_documents(self):
        """Pessoa física não tem contrato social nem cartão CNPJ."""
        if self.document_type_chosen == Company.DocumentType.CPF:
            return ("document_file", "address_proof")
        return COMPANY_DOCUMENTS

    def clean(self):
        cleaned = super().clean()
        self.validate_documents(self.required_documents)
        return cleaned

    def save(self, commit=True):
        company = super().save(False)
        company.registered_at = company.registered_at or timezone.now()
        if commit:
            company.save()
        return company


class PasswordFieldsMixin(forms.Form):
    password1 = forms.CharField(label="Senha", widget=forms.PasswordInput, required=False)
    password2 = forms.CharField(label="Repita a senha", widget=forms.PasswordInput, required=False)

    def clean(self):
        cleaned = super().clean()
        first, second = cleaned.get("password1"), cleaned.get("password2")
        if self.password_required and not first:
            self.add_error("password1", "Defina uma senha para o primeiro acesso.")
        if first and first != second:
            self.add_error("password2", "As senhas não conferem.")
        if first and first == second:
            try:
                validate_password(first)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned

    @property
    def password_required(self):
        return self.instance.pk is None


class CompanyUserForm(PasswordFieldsMixin, forms.ModelForm):
    """Usuário de uma empresa contratante. O e-mail é o login."""

    class Meta:
        model = User
        fields = ("email", "first_name", "last_name", "role", "is_active")

    def __init__(self, *args, company=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company or getattr(self.instance, "company", None)
        self.fields["email"].required = True
        self.fields["email"].label = "E-mail (login)"
        self.fields["role"].choices = [(value, label) for value, label in User.Role.choices if value in User.COMPANY_ROLES]
        if self.instance.pk is None:
            self.fields["role"].initial = User.Role.ADMIN

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        duplicated = User.objects.filter(username=email)
        if self.instance.pk:
            duplicated = duplicated.exclude(pk=self.instance.pk)
        if duplicated.exists():
            raise forms.ValidationError("Já existe um usuário com este e-mail.")
        return email

    def save(self, commit=True):
        user = super().save(False)
        user.username = user.email
        user.company = self.company
        password = self.cleaned_data.get("password1")
        if password:
            user.set_password(password)
        if commit:
            user.save()
        return user


class PlatformUserForm(CompanyUserForm):
    """Equipe interna: admin master ou operador da central."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["role"].choices = [(value, label) for value, label in User.Role.choices if value in User.PLATFORM_ROLES]
        if self.instance.pk is None:
            self.fields["role"].initial = User.Role.DISPATCHER


class SetPasswordForm(forms.Form):
    password1 = forms.CharField(label="Nova senha", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Repita a nova senha", widget=forms.PasswordInput)

    def clean(self):
        cleaned = super().clean()
        first, second = cleaned.get("password1"), cleaned.get("password2")
        if first and first != second:
            self.add_error("password2", "As senhas não conferem.")
        elif first:
            try:
                validate_password(first)
            except ValidationError as error:
                self.add_error("password1", error)
        return cleaned
