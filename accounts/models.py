from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from core.uploads import company_document_path, validate_document_file


class CompanyQuerySet(models.QuerySet):
    def clients(self):
        return self.filter(is_platform=False)

    def platform(self):
        return self.filter(is_platform=True).first()


class Company(models.Model):
    class DocumentType(models.TextChoices):
        CNPJ = "cnpj", "CNPJ"
        MEI = "mei", "MEI"
        CPF = "cpf", "CPF"

    class TaxRegime(models.TextChoices):
        SIMPLES = "simples", "Simples Nacional"
        MEI = "mei", "MEI"
        PRESUMIDO = "presumido", "Lucro presumido"
        REAL = "real", "Lucro real"
        PF = "pf", "Pessoa física"

    # MEI também possui CNPJ, então os dois faturam em boleto. Pessoa física paga por entrega.
    INVOICEABLE_DOCUMENTS = (DocumentType.CNPJ, DocumentType.MEI)

    name = models.CharField("nome fantasia", max_length=160)
    legal_name = models.CharField("razão social / nome completo", max_length=200, blank=True)
    document_type = models.CharField("tipo de documento", max_length=4, choices=DocumentType.choices, default=DocumentType.CNPJ)
    document = models.CharField("CNPJ / CPF", max_length=18, unique=True)
    state_registration = models.CharField("inscrição estadual", max_length=30, blank=True)
    municipal_registration = models.CharField("inscrição municipal", max_length=30, blank=True)
    tax_regime = models.CharField("regime tributário", max_length=10, choices=TaxRegime.choices, blank=True)
    founded_on = models.DateField("data de abertura", null=True, blank=True)
    business_area = models.CharField("ramo de atividade", max_length=120, blank=True)
    slug = models.SlugField(unique=True)
    email = models.EmailField("e-mail de contato", blank=True)
    phone = models.CharField("telefone", max_length=30, blank=True)
    contact_name = models.CharField("responsável", max_length=160, blank=True)
    contact_document = models.CharField("CPF do responsável", max_length=14, blank=True)
    contact_role = models.CharField("cargo do responsável", max_length=90, blank=True)
    zip_code = models.CharField("CEP", max_length=10, blank=True)
    address = models.CharField("logradouro e número", max_length=255, blank=True)
    complement = models.CharField("complemento", max_length=90, blank=True)
    district = models.CharField("bairro", max_length=90, blank=True)
    city = models.CharField("cidade", max_length=90, blank=True)
    state = models.CharField("UF", max_length=2, blank=True)
    billing_email = models.EmailField("e-mail do financeiro", blank=True)
    billing_phone = models.CharField("telefone do financeiro", max_length=30, blank=True)
    invoice_due_day = models.PositiveSmallIntegerField(
        "dia de vencimento preferido", default=10,
        validators=[MinValueValidator(1), MaxValueValidator(28)],
        help_text="Usado como sugestão ao faturar entregas em boleto.",
    )

    document_file = models.FileField(
        "cartão CNPJ ou documento do titular", upload_to=company_document_path, blank=True,
        validators=[validate_document_file],
    )
    articles_of_association = models.FileField(
        "contrato social ou certificado MEI", upload_to=company_document_path, blank=True,
        validators=[validate_document_file],
    )
    address_proof = models.FileField(
        "comprovante de endereço", upload_to=company_document_path, blank=True,
        validators=[validate_document_file],
        help_text="Conta de água, luz ou telefone dos últimos três meses.",
    )
    contact_document_file = models.FileField(
        "documento com foto do responsável", upload_to=company_document_path, blank=True,
        validators=[validate_document_file],
    )

    notes = models.TextField("observações internas", blank=True)
    registered_at = models.DateTimeField(
        "cadastro concluído em", null=True, blank=True,
        help_text="Enquanto estiver vazio, a empresa só acessa a própria tela de cadastro.",
    )
    is_active = models.BooleanField("ativa", default=True)
    is_platform = models.BooleanField(
        "transportadora da plataforma", default=False,
        help_text="Marque somente para a SC Transporte Executivo Delivery. A frota e os entregadores pertencem a ela.",
    )
    created_at = models.DateTimeField("criada em", auto_now_add=True)

    DOCUMENTS = ("document_file", "articles_of_association", "address_proof", "contact_document_file")

    objects = CompanyQuerySet.as_manager()

    class Meta:
        verbose_name = "empresa"
        verbose_name_plural = "empresas"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["is_platform"], condition=models.Q(is_platform=True), name="single_platform_company",
            )
        ]

    def __str__(self):
        return self.name

    @property
    def document_label(self):
        return f"{self.get_document_type_display()} {self.document}"

    @property
    def can_invoice(self):
        """Somente CNPJ e MEI podem faturar as entregas em boleto."""
        return self.document_type in self.INVOICEABLE_DOCUMENTS

    @property
    def is_registered(self):
        return self.registered_at is not None

    @property
    def full_address(self):
        parts = [self.address, self.complement, self.district,
                 self.city and f"{self.city}/{self.state}".strip("/"), self.zip_code]
        return " · ".join(part for part in parts if part)

    @property
    def documents(self):
        """Pares (rótulo, campo, arquivo) dos anexos já enviados."""
        return [
            (self._meta.get_field(name).verbose_name, name, getattr(self, name))
            for name in self.DOCUMENTS
            if getattr(self, name)
        ]

    @property
    def required_documents(self):
        """Pessoa física não tem contrato social."""
        if self.document_type == self.DocumentType.CPF:
            return ("document_file", "address_proof")
        return ("document_file", "articles_of_association", "address_proof", "contact_document_file")

    @property
    def missing_documents(self):
        return [
            self._meta.get_field(name).verbose_name
            for name in self.required_documents
            if not getattr(self, name)
        ]

    @property
    def billing_contact(self):
        return self.billing_email or self.email

    @property
    def billing_name(self):
        return self.legal_name or self.name

    def mark_registered(self):
        if self.registered_at is None:
            self.registered_at = timezone.now()
            self.save(update_fields=["registered_at"])


class User(AbstractUser):
    class Role(models.TextChoices):
        MASTER = "master", "Admin master"
        DISPATCHER = "dispatcher", "Central de despacho"
        OWNER = "owner", "Proprietário"
        ADMIN = "admin", "Administrador"
        OPERATOR = "operator", "Operador"
        VIEWER = "viewer", "Visualizador"
        DRIVER = "driver", "Entregador"

    COMPANY_ROLES = (Role.OWNER, Role.ADMIN, Role.OPERATOR, Role.VIEWER)
    PLATFORM_ROLES = (Role.MASTER, Role.DISPATCHER)

    company = models.ForeignKey(
        Company, verbose_name="empresa", on_delete=models.PROTECT,
        related_name="users", null=True, blank=True,
    )
    role = models.CharField("papel", max_length=12, choices=Role.choices, default=Role.VIEWER)

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    @property
    def is_master(self):
        """Admin master do sistema: cadastra empresas e enxerga tudo."""
        return self.is_superuser or self.role == self.Role.MASTER

    @property
    def is_platform_staff(self):
        """Equipe da SC Transporte Executivo Delivery: vê as solicitações de todas as empresas."""
        return self.is_superuser or self.role in self.PLATFORM_ROLES

    @property
    def is_driver(self):
        return self.role == self.Role.DRIVER

    @property
    def can_manage_companies(self):
        return self.is_master

    @property
    def can_manage_deliveries(self):
        return self.is_superuser or self.role in {self.Role.MASTER, self.Role.DISPATCHER, self.Role.OWNER, self.Role.ADMIN, self.Role.OPERATOR}

    @property
    def can_manage_resources(self):
        """Só o admin master cadastra entregadores e veículos."""
        return self.is_master

    @property
    def can_manage_company_profile(self):
        """Quem responde pelo cadastro e pelo faturamento da empresa."""
        return self.is_superuser or self.role in {self.Role.MASTER, self.Role.OWNER, self.Role.ADMIN}
