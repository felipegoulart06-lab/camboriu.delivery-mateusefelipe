import uuid
from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from accounts.models import Company
from core.uploads import document_path, validate_document_file

LATITUDE_VALIDATORS = [MinValueValidator(-90), MaxValueValidator(90)]
LONGITUDE_VALIDATORS = [MinValueValidator(-180), MaxValueValidator(180)]


def checklist_photo_path(instance, filename):
    extension = filename.rsplit(".", 1)[-1].lower()[:5] if "." in filename else "jpg"
    delivery = instance.checklist.delivery
    return f"checklists/{delivery.company_id}/{delivery.code}/{instance.slot}-{uuid.uuid4().hex[:8]}.{extension}"


class TenantModel(models.Model):
    company = models.ForeignKey(Company, verbose_name="empresa", on_delete=models.PROTECT)

    class Meta:
        abstract = True


class Driver(TenantModel):
    class Status(models.TextChoices):
        ACTIVE = "active", "Ativo"
        INACTIVE = "inactive", "Inativo"
        AWAY = "away", "Afastado"
    class Contract(models.TextChoices):
        EMPLOYEE = "employee", "CLT"
        CONTRACTOR = "contractor", "Prestador"
        PARTNER = "partner", "Parceiro"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, verbose_name="usuário de acesso", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="driver_profile",
        help_text="Conta usada pelo entregador para entrar no painel dele.",
    )
    name = models.CharField("nome completo", max_length=160)
    cpf = models.CharField("CPF", max_length=14)
    birth_date = models.DateField("data de nascimento", null=True, blank=True)
    rg = models.CharField("RG", max_length=20, blank=True)
    rg_issuer = models.CharField("órgão emissor do RG", max_length=20, blank=True)
    mother_name = models.CharField("nome da mãe", max_length=160, blank=True)
    phone = models.CharField("telefone", max_length=30)
    emergency_contact = models.CharField("contato de emergência", max_length=160, blank=True)
    emergency_phone = models.CharField("telefone de emergência", max_length=30, blank=True)

    zip_code = models.CharField("CEP", max_length=10, blank=True)
    address = models.CharField("logradouro e número", max_length=255, blank=True)
    district = models.CharField("bairro", max_length=90, blank=True)
    city = models.CharField("cidade", max_length=90, blank=True)
    state = models.CharField("UF", max_length=2, blank=True)

    cnh = models.CharField("número da CNH", max_length=20)
    cnh_category = models.CharField("categoria CNH", max_length=5)
    cnh_register = models.CharField("nº de registro da CNH", max_length=20, blank=True)
    cnh_state = models.CharField("UF da CNH", max_length=2, blank=True)
    cnh_issued_at = models.DateField("data de emissão da CNH", null=True, blank=True)
    cnh_first_license_at = models.DateField("data da primeira habilitação", null=True, blank=True)
    cnh_has_ear = models.BooleanField(
        "CNH com EAR (exerce atividade remunerada)", default=False,
        help_text="Obrigatório para transportar carga de terceiros.",
    )
    cnh_expires_at = models.DateField("vencimento da CNH", null=True, blank=True)
    medical_exam_expires_at = models.DateField("vencimento do exame", null=True, blank=True)

    status = models.CharField(max_length=12, choices=Status.choices, default=Status.ACTIVE)
    contract_type = models.CharField("vínculo", max_length=15, choices=Contract.choices)
    pix_key = models.CharField("chave Pix para repasse", max_length=140, blank=True)
    bank_name = models.CharField("banco", max_length=90, blank=True)
    bank_agency = models.CharField("agência", max_length=15, blank=True)
    bank_account = models.CharField("conta", max_length=25, blank=True)

    cnh_front = models.FileField(
        "CNH — frente ou CNH digital", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
    )
    cnh_back = models.FileField(
        "CNH — verso", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
    )
    proof_of_address = models.FileField(
        "comprovante de residência", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
        help_text="Conta de água, luz ou telefone dos últimos três meses.",
    )
    portrait = models.FileField(
        "foto do entregador", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
    )
    criminal_record = models.FileField(
        "certidão de antecedentes criminais", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
    )
    medical_certificate = models.FileField(
        "atestado ou exame médico (ASO)", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
    )
    bank_proof = models.FileField(
        "comprovante bancário", upload_to=document_path("entregadores"), blank=True,
        validators=[validate_document_file],
    )

    last_lat = models.FloatField("última latitude", null=True, blank=True, validators=LATITUDE_VALIDATORS)
    last_lng = models.FloatField("última longitude", null=True, blank=True, validators=LONGITUDE_VALIDATORS)
    last_position_at = models.DateTimeField("posição atualizada em", null=True, blank=True)
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    DOCUMENTS = ("cnh_front", "cnh_back", "proof_of_address", "portrait", "criminal_record", "medical_certificate", "bank_proof")
    REQUIRED_DOCUMENTS = ("cnh_front", "proof_of_address", "portrait")

    class Meta:
        verbose_name = "motorista"
        verbose_name_plural = "motoristas"
        ordering = ["name"]
        constraints = [models.UniqueConstraint(fields=["company", "cpf"], name="unique_driver_cpf_company")]

    def __str__(self):
        return self.name

    @property
    def whatsapp_url(self):
        digits = "".join(char for char in self.phone if char.isdigit())
        if not digits:
            return ""
        if not digits.startswith("55"):
            digits = f"55{digits}"
        return f"https://wa.me/{digits}"

    @property
    def has_position(self):
        return self.last_lat is not None and self.last_lng is not None

    @property
    def full_address(self):
        parts = [self.address, self.district, self.city and f"{self.city}/{self.state}" or ""]
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
    def missing_documents(self):
        return [
            self._meta.get_field(name).verbose_name
            for name in self.REQUIRED_DOCUMENTS
            if not getattr(self, name)
        ]

    @property
    def is_documentation_complete(self):
        return not self.missing_documents

    def expiring(self, reference=None):
        """CNH e exame médico vencidos ou a vencer em 30 dias."""
        today = reference or timezone.localdate()
        limit = today + timedelta(days=30)
        alerts = []
        for field, label in (("cnh_expires_at", "CNH"), ("medical_exam_expires_at", "Exame médico")):
            value = getattr(self, field)
            if value and value <= limit:
                alerts.append((label, value, value < today))
        return alerts

    def register_position(self, lat, lng):
        self.last_lat, self.last_lng, self.last_position_at = lat, lng, timezone.now()
        self.save(update_fields=["last_lat", "last_lng", "last_position_at"])

    @property
    def masked_cpf(self):
        """CPF visível para a empresa: 064.3**.***-**."""
        digits = "".join(char for char in (self.cpf or "") if char.isdigit())
        if len(digits) >= 11:
            return f"{digits[:3]}.{digits[3]}**.***-**"
        if len(digits) >= 4:
            return f"{digits[:3]}.{digits[3]}**.***-**"
        return "***.***.***-**"

    @property
    def tenure_label(self):
        """Há quanto tempo o entregador está na operação, sem expor a ficha."""
        start = timezone.localdate()
        if self.created_at:
            start = timezone.localtime(self.created_at).date()
        days = max((timezone.localdate() - start).days, 0)
        if days < 1:
            return "desde hoje na operação"
        if days == 1:
            return "há 1 dia na operação"
        if days < 30:
            return f"há {days} dias na operação"
        months = days // 30
        if months == 1:
            return "há 1 mês na operação"
        if months < 12:
            return f"há {months} meses na operação"
        years = months // 12
        if years == 1:
            return "há 1 ano na operação"
        return f"há {years} anos na operação"


class Vehicle(TenantModel):
    class Kind(models.TextChoices):
        MOTORCYCLE = "motorcycle", "Moto"
        CAR = "car", "Carro"
        UTILITY = "utility", "Utilitário"
    class Status(models.TextChoices):
        AVAILABLE = "available", "Disponível"
        IN_USE = "in_use", "Em uso"
        MAINTENANCE = "maintenance", "Manutenção"
        INACTIVE = "inactive", "Inativo"
    class Fuel(models.TextChoices):
        FLEX = "flex", "Flex"
        GASOLINE = "gasoline", "Gasolina"
        ETHANOL = "ethanol", "Etanol"
        DIESEL = "diesel", "Diesel"
        ELECTRIC = "electric", "Elétrico"
        HYBRID = "hybrid", "Híbrido"
    class Body(models.TextChoices):
        VAN = "van", "Furgão"
        BOX = "box", "Baú"
        OPEN = "open", "Carroceria aberta"
        REFRIGERATED = "refrigerated", "Refrigerado"

    kind = models.CharField("tipo", max_length=12, choices=Kind.choices)
    plate = models.CharField("placa", max_length=10)
    plate_state = models.CharField("UF da placa", max_length=2, blank=True)
    renavam = models.CharField("RENAVAM", max_length=11, blank=True)
    chassis = models.CharField("chassi", max_length=17, blank=True)
    brand = models.CharField("marca", max_length=60)
    model = models.CharField("modelo", max_length=80)
    year = models.PositiveSmallIntegerField("ano de fabricação")
    model_year = models.PositiveSmallIntegerField("ano do modelo", null=True, blank=True)
    color = models.CharField("cor", max_length=30, blank=True)
    fuel = models.CharField("combustível", max_length=10, choices=Fuel.choices, blank=True)
    mileage_km = models.PositiveIntegerField("quilometragem atual", null=True, blank=True)
    capacity_kg = models.DecimalField("capacidade (kg)", max_digits=8, decimal_places=2, null=True, blank=True)
    equipment = models.CharField("baú/equipamentos", max_length=255, blank=True)
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.AVAILABLE)

    owner_name = models.CharField("proprietário no CRLV", max_length=160, blank=True)
    owner_document = models.CharField("CPF/CNPJ do proprietário", max_length=18, blank=True)
    crlv_expires_at = models.DateField("vencimento do licenciamento", null=True, blank=True)
    insurer = models.CharField("seguradora", max_length=90, blank=True)
    insurance_policy = models.CharField("número da apólice", max_length=60, blank=True)
    insurance_expires_at = models.DateField("vencimento do seguro", null=True, blank=True)
    has_tracker = models.BooleanField("possui rastreador", default=False)
    tracker_provider = models.CharField("empresa do rastreador", max_length=90, blank=True)

    # Específicos por tipo, cobrados no formulário conforme a escolha.
    top_case_liters = models.PositiveSmallIntegerField("capacidade do baú (litros)", null=True, blank=True)
    doors = models.PositiveSmallIntegerField("número de portas", null=True, blank=True)
    body_type = models.CharField("tipo de carroceria", max_length=14, choices=Body.choices, blank=True)
    gross_weight_kg = models.DecimalField("peso bruto total (kg)", max_digits=9, decimal_places=2, null=True, blank=True)
    cargo_length_cm = models.PositiveSmallIntegerField("comprimento do compartimento (cm)", null=True, blank=True)
    cargo_width_cm = models.PositiveSmallIntegerField("largura do compartimento (cm)", null=True, blank=True)
    cargo_height_cm = models.PositiveSmallIntegerField("altura do compartimento (cm)", null=True, blank=True)
    refrigerated = models.BooleanField("compartimento refrigerado", default=False)
    lockable = models.BooleanField("compartimento com trava", default=False)

    crlv_document = models.FileField(
        "CRLV digital", upload_to=document_path("veiculos"), blank=True,
        validators=[validate_document_file],
    )
    insurance_document = models.FileField(
        "apólice do seguro", upload_to=document_path("veiculos"), blank=True,
        validators=[validate_document_file],
    )
    photo_front = models.FileField(
        "foto frontal", upload_to=document_path("veiculos"), blank=True,
        validators=[validate_document_file],
    )
    photo_rear = models.FileField(
        "foto traseira", upload_to=document_path("veiculos"), blank=True,
        validators=[validate_document_file],
    )
    photo_plate = models.FileField(
        "foto da placa", upload_to=document_path("veiculos"), blank=True,
        validators=[validate_document_file],
    )
    photo_cargo = models.FileField(
        "foto do compartimento de carga", upload_to=document_path("veiculos"), blank=True,
        validators=[validate_document_file],
    )
    notes = models.TextField("observações", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    DOCUMENTS = ("crlv_document", "insurance_document", "photo_front", "photo_rear", "photo_plate", "photo_cargo")

    class Meta:
        verbose_name = "veículo"
        verbose_name_plural = "veículos"
        ordering = ["plate"]
        constraints = [models.UniqueConstraint(fields=["company", "plate"], name="unique_vehicle_plate_company")]

    def __str__(self):
        return f"{self.plate} · {self.model}"

    @property
    def documents(self):
        """Pares (rótulo, arquivo) dos anexos já enviados."""
        return [
            (self._meta.get_field(name).verbose_name, name, getattr(self, name))
            for name in self.DOCUMENTS
            if getattr(self, name)
        ]

    @property
    def missing_documents(self):
        return [self._meta.get_field(name).verbose_name for name in self.DOCUMENTS if not getattr(self, name)]

    @property
    def cargo_volume_liters(self):
        dimensions = (self.cargo_length_cm, self.cargo_width_cm, self.cargo_height_cm)
        if not all(dimensions):
            return None
        return round(self.cargo_length_cm * self.cargo_width_cm * self.cargo_height_cm / 1000)

    @property
    def public_label(self):
        """O que a empresa pode ver: modelo, placa e cor."""
        parts = [f"{self.brand} {self.model}".strip(), self.plate]
        if self.color:
            parts.append(self.color)
        return " · ".join(parts)

    @property
    def public_expiry_label(self):
        crlv = self.crlv_expires_at.strftime("%d/%m/%Y") if self.crlv_expires_at else "—"
        insurance = self.insurance_expires_at.strftime("%d/%m/%Y") if self.insurance_expires_at else "—"
        return f"Licenciamento {crlv} · Seguro {insurance}"

    def expiring(self, reference=None):
        """Documentos vencidos ou a vencer em 30 dias."""
        today = reference or timezone.localdate()
        limit = today + timedelta(days=30)
        alerts = []
        for field, label in (("crlv_expires_at", "Licenciamento"), ("insurance_expires_at", "Seguro")):
            value = getattr(self, field)
            if value and value <= limit:
                alerts.append((label, value, value < today))
        return alerts


class DeliveryQuerySet(models.QuerySet):
    """Solicitações da empresa não saem do banco: só mudam de status."""

    def delete(self):
        if not self.exists():
            return 0, {}
        raise ProtectedError(
            "Solicitações de entrega não podem ser excluídas. Cancele a corrida para encerrar o atendimento; o histórico permanece.",
            set(self),
        )

    def hard_delete(self):
        """Saída única para a limpeza dos dados de demonstração (manage.py purge_demo).

        Nenhuma tela do sistema chama isso: no painel a entrega só é cancelada.
        """
        return super().delete()


class Delivery(TenantModel):
    class ItemType(models.TextChoices):
        DOCUMENT = "document", "Documento"
        HIGH_VALUE = "high_value", "Alto valor"
        MEDICINE = "medicine", "Medicamento"
        SAMPLE = "sample", "Amostra"
        OTHER = "other", "Outro"
    class Priority(models.TextChoices):
        NORMAL = "normal", "Normal"
        URGENT = "urgent", "Urgente"
        CRITICAL = "critical", "Crítica"
    class Status(models.TextChoices):
        REQUESTED = "requested", "Solicitada"
        DISPATCHING = "dispatching", "Acionando entregador"
        ACCEPTED = "accepted", "Aceita pelo entregador"
        APPROVED = "approved", "Aprovada"
        PICKUP = "pickup", "Em coleta"
        IN_TRANSIT = "in_transit", "Em trânsito"
        DELIVERED = "delivered", "Entregue"
        CANCELED = "canceled", "Cancelada"

    OPEN_STATUSES = (Status.REQUESTED, Status.DISPATCHING)
    ACTIVE_STATUSES = (Status.DISPATCHING, Status.ACCEPTED, Status.APPROVED, Status.PICKUP, Status.IN_TRANSIT)
    TRACKABLE_STATUSES = (Status.ACCEPTED, Status.APPROVED, Status.PICKUP, Status.IN_TRANSIT)
    CLOSED_STATUSES = (Status.DELIVERED, Status.CANCELED)

    code = models.CharField("código", max_length=24, unique=True, editable=False)
    requester = models.CharField("cliente solicitante", max_length=160)
    item_type = models.CharField("tipo de item", max_length=15, choices=ItemType.choices)
    description = models.TextField("descrição")
    declared_value = models.DecimalField("valor declarado", max_digits=12, decimal_places=2, default=0)
    confidential = models.BooleanField("sigiloso", default=False)
    pickup_address = models.CharField("endereço de coleta", max_length=255)
    pickup_contact = models.CharField("contato da coleta", max_length=160)
    pickup_lat = models.FloatField("latitude da coleta", null=True, blank=True, validators=LATITUDE_VALIDATORS)
    pickup_lng = models.FloatField("longitude da coleta", null=True, blank=True, validators=LONGITUDE_VALIDATORS)
    delivery_address = models.CharField("endereço de entrega", max_length=255)
    delivery_contact = models.CharField("contato da entrega", max_length=160)
    delivery_lat = models.FloatField("latitude da entrega", null=True, blank=True, validators=LATITUDE_VALIDATORS)
    delivery_lng = models.FloatField("longitude da entrega", null=True, blank=True, validators=LONGITUDE_VALIDATORS)
    pickup_window = models.DateTimeField("janela de coleta", null=True, blank=True)
    deadline = models.DateTimeField("prazo", null=True, blank=True)
    priority = models.CharField("prioridade", max_length=10, choices=Priority.choices, default=Priority.NORMAL)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.REQUESTED)
    driver = models.ForeignKey(Driver, verbose_name="motorista", on_delete=models.PROTECT, null=True, blank=True)
    vehicle = models.ForeignKey(Vehicle, verbose_name="veículo", on_delete=models.PROTECT, null=True, blank=True)
    proof = models.CharField("comprovante", max_length=255, blank=True)
    receiver = models.CharField("recebedor", max_length=160, blank=True)
    notes = models.TextField("observações", blank=True)
    price = models.DecimalField(
        "valor cobrado da empresa", max_digits=10, decimal_places=2, default=0,
        help_text="Calculado pela tabela de preços e ajustável pelo admin master.",
    )
    driver_payout_amount = models.DecimalField("valor a repassar ao entregador", max_digits=10, decimal_places=2, default=0)
    invoice = models.ForeignKey(
        "finance.Invoice", verbose_name="fatura", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="deliveries",
    )
    payout = models.ForeignKey(
        "finance.DriverPayout", verbose_name="repasse", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="deliveries",
    )
    created_at = models.DateTimeField("criada em", auto_now_add=True)
    updated_at = models.DateTimeField("atualizada em", auto_now=True)
    dispatched_at = models.DateTimeField("acionada em", null=True, blank=True)
    accepted_at = models.DateTimeField("aceita em", null=True, blank=True)
    master_confirmed_at = models.DateTimeField("confirmada pela central", null=True, blank=True)
    picked_up_at = models.DateTimeField("coletada em", null=True, blank=True)
    delivered_at = models.DateTimeField("entregue em", null=True, blank=True)

    class Meta:
        verbose_name = "entrega"
        verbose_name_plural = "entregas"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "created_at"]),
            # Fila do painel da plataforma e lista de corridas do entregador.
            models.Index(fields=["status", "-created_at"], name="delivery_status_recentes"),
            models.Index(fields=["driver", "status"], name="delivery_por_entregador"),
        ]

    objects = DeliveryQuerySet.as_manager()

    def clean(self):
        errors = {}
        if self.driver_id and not self._belongs_to_operation(self.driver):
            errors["driver"] = "O motorista deve ser da sua empresa ou da frota da SC Transporte Executivo Delivery."
        if self.vehicle_id and not self._belongs_to_operation(self.vehicle):
            errors["vehicle"] = "O veículo deve ser da sua empresa ou da frota da SC Transporte Executivo Delivery."
        if self.deadline and self.pickup_window and self.deadline < self.pickup_window:
            errors["deadline"] = "O prazo não pode ser anterior à coleta."
        if errors:
            raise ValidationError(errors)

    def _belongs_to_operation(self, resource):
        return resource.company_id == self.company_id or resource.company.is_platform

    def save(self, *args, **kwargs):
        now = timezone.now()
        if not self.code:
            self.code = f"CD-{timezone.localdate():%y%m%d}-{uuid.uuid4().hex[:6].upper()}"
        if self.status == self.Status.DISPATCHING and not self.dispatched_at:
            self.dispatched_at = now
        if self.status == self.Status.ACCEPTED and not self.accepted_at:
            self.accepted_at = now
        if self.status == self.Status.IN_TRANSIT and not self.picked_up_at:
            self.picked_up_at = now
        if self.status == self.Status.DELIVERED and not self.delivered_at:
            self.delivered_at = now
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, using=None, keep_parents=False):
        raise ProtectedError(
            "Solicitações de entrega não podem ser excluídas. Cancele a corrida para encerrar o atendimento; o histórico permanece.",
            {self},
        )

    def __str__(self):
        return self.code

    @property
    def is_open(self):
        return self.status in self.OPEN_STATUSES

    @property
    def is_trackable(self):
        """Só publica a posição do entregador enquanto a corrida está em execução."""
        return self.status in self.TRACKABLE_STATUSES and self.driver_id is not None

    @property
    def has_pickup_checklist(self):
        return hasattr(self, "pickup_checklist") and self.pickup_checklist.is_submitted

    @property
    def destinations(self):
        """O endereço principal é a primeira parada; as demais vêm de DeliveryStop."""
        first = DeliveryStop(delivery=self, order=1, address=self.delivery_address, contact=self.delivery_contact,
                             lat=self.delivery_lat, lng=self.delivery_lng, receiver=self.receiver,
                             delivered_at=self.delivered_at)
        return [first, *self.stops.all()]

    @property
    def destination_count(self):
        return 1 + self.stops.count()

    @property
    def is_multi_stop(self):
        return self.destination_count > 1

    @property
    def platform_margin(self):
        return self.price - self.driver_payout_amount

    @property
    def is_billable(self):
        """Entregue e ainda sem fatura: pode entrar em um boleto."""
        return self.status == self.Status.DELIVERED and self.invoice_id is None and self.price > 0

    @property
    def is_master_confirmed(self):
        """A empresa só vê pedido aceito e PDF depois que a central confirma entregador e veículo."""
        return self.master_confirmed_at is not None

    @property
    def company_status_code(self):
        if not self.is_master_confirmed and self.status in (
            self.Status.REQUESTED, self.Status.DISPATCHING, self.Status.ACCEPTED, self.Status.APPROVED,
        ):
            return self.Status.REQUESTED if self.status == self.Status.REQUESTED else "pending_confirm"
        return self.status

    @property
    def company_status_label(self):
        if not self.is_master_confirmed:
            if self.status == self.Status.REQUESTED:
                return "Solicitada"
            if self.status in (self.Status.DISPATCHING, self.Status.ACCEPTED, self.Status.APPROVED):
                return "Aguardando confirmação da central"
        if self.status == self.Status.ACCEPTED:
            return "Pedido aceito"
        return self.get_status_display()

    def register_event(self, description, user=None):
        return DeliveryEvent.objects.create(
            company=self.company, delivery=self, status=self.status, description=description, created_by=user,
        )


class DeliveryStop(models.Model):
    """Destino adicional: uma viagem pode deixar itens em vários endereços."""

    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="stops")
    order = models.PositiveSmallIntegerField("ordem", default=2)
    address = models.CharField("endereço de entrega", max_length=255)
    contact = models.CharField("contato no destino", max_length=160, blank=True)
    lat = models.FloatField("latitude", null=True, blank=True, validators=LATITUDE_VALIDATORS)
    lng = models.FloatField("longitude", null=True, blank=True, validators=LONGITUDE_VALIDATORS)
    notes = models.CharField("observações do destino", max_length=255, blank=True)
    receiver = models.CharField("recebedor", max_length=160, blank=True)
    delivered_at = models.DateTimeField("entregue em", null=True, blank=True)

    class Meta:
        verbose_name = "destino da entrega"
        verbose_name_plural = "destinos da entrega"
        ordering = ["order", "pk"]

    def __str__(self):
        return f"{self.order}. {self.address}"


class DeliveryEvent(TenantModel):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="events")
    status = models.CharField(max_length=12, choices=Delivery.Status.choices)
    description = models.CharField("descrição", max_length=255)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "evento da entrega"
        verbose_name_plural = "eventos das entregas"
        ordering = ["-created_at"]
        # A linha do tempo da entrega é aberta em quase toda tela de detalhe.
        indexes = [models.Index(fields=["delivery", "-created_at"], name="evento_por_entrega")]

    def clean(self):
        if self.delivery_id and self.delivery.company_id != self.company_id:
            raise ValidationError("O evento deve pertencer à empresa da entrega.")

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class DriverPing(models.Model):
    """Posição enviada pelo aparelho do entregador durante a corrida."""

    driver = models.ForeignKey(Driver, verbose_name="motorista", on_delete=models.CASCADE, related_name="pings")
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE, related_name="pings", null=True, blank=True)
    lat = models.FloatField("latitude", validators=LATITUDE_VALIDATORS)
    lng = models.FloatField("longitude", validators=LONGITUDE_VALIDATORS)
    accuracy = models.FloatField("precisão (m)", null=True, blank=True)
    speed = models.FloatField("velocidade (m/s)", null=True, blank=True)
    heading = models.FloatField("direção", null=True, blank=True)
    recorded_at = models.DateTimeField("registrado em", auto_now_add=True)

    class Meta:
        verbose_name = "posição do motorista"
        verbose_name_plural = "posições dos motoristas"
        ordering = ["-recorded_at"]
        indexes = [models.Index(fields=["delivery", "recorded_at"]), models.Index(fields=["driver", "recorded_at"])]

    def __str__(self):
        return f"{self.driver} · {self.recorded_at:%d/%m %H:%M}"


class PickupChecklist(TenantModel):
    """Procedimento antifraude preenchido pelo entregador no momento da coleta."""

    delivery = models.OneToOneField(Delivery, on_delete=models.CASCADE, related_name="pickup_checklist")
    driver = models.ForeignKey(Driver, verbose_name="motorista", on_delete=models.PROTECT, related_name="checklists")
    handover_name = models.CharField("responsável que entregou o item", max_length=160)
    handover_document = models.CharField("documento do responsável (RG/CPF)", max_length=30)
    package_count = models.PositiveSmallIntegerField("volumes conferidos", default=1)
    seal_number = models.CharField("número do lacre", max_length=60, blank=True)
    identity_checked = models.BooleanField("confirmei a identidade do responsável pela entrega")
    item_matches_request = models.BooleanField("o item confere com a solicitação da empresa")
    packaging_intact = models.BooleanField("embalagem íntegra, sem sinal de violação")
    seal_applied = models.BooleanField("lacre/selo aplicado e fotografado")
    documents_checked = models.BooleanField("nota fiscal ou documento de acompanhamento conferido")
    photos_are_original = models.BooleanField("declaro que as fotos foram tiradas agora, neste local")
    temperature_ok = models.BooleanField("acondicionamento térmico adequado", default=False, blank=True)
    notes = models.TextField("observações da coleta", blank=True)
    lat = models.FloatField("latitude da coleta", null=True, blank=True, validators=LATITUDE_VALIDATORS)
    lng = models.FloatField("longitude da coleta", null=True, blank=True, validators=LONGITUDE_VALIDATORS)
    accuracy = models.FloatField("precisão (m)", null=True, blank=True)
    device = models.CharField("dispositivo", max_length=255, blank=True)
    created_at = models.DateTimeField("iniciado em", auto_now_add=True)
    submitted_at = models.DateTimeField("enviado em", null=True, blank=True)

    class Meta:
        verbose_name = "checklist de coleta"
        verbose_name_plural = "checklists de coleta"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Checklist {self.delivery.code}"

    @property
    def is_submitted(self):
        return self.submitted_at is not None

    @property
    def required_photo_slots(self):
        return [slot for slot, _ in ChecklistPhoto.Slot.choices]

    @property
    def missing_photo_slots(self):
        sent = set(self.photos.values_list("slot", flat=True))
        return [slot for slot in self.required_photo_slots if slot not in sent]

    def clean(self):
        errors = {}
        if self.delivery_id and self.delivery.company_id != self.company_id:
            errors["company"] = "O checklist deve pertencer à empresa da entrega."
        if self.delivery_id and self.driver_id and self.delivery.driver_id != self.driver_id:
            errors["driver"] = "Somente o entregador designado pode preencher o checklist."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


class ChecklistPhoto(models.Model):
    """Uma foto por etapa do checklist: são 12 registros obrigatórios."""

    class Slot(models.TextChoices):
        SITE = "01-local", "1 · Fachada ou recepção do local de coleta"
        DOCUMENT = "02-documento", "2 · Nota fiscal ou documento de acompanhamento"
        ITEM_OVERVIEW = "03-item-geral", "3 · Item — visão geral"
        ITEM_LABEL = "04-item-etiqueta", "4 · Item — etiqueta ou identificação"
        ITEM_SIDE_A = "05-item-lado-a", "5 · Item — lado A"
        ITEM_SIDE_B = "06-item-lado-b", "6 · Item — lado B"
        PACKAGING = "07-embalagem", "7 · Embalagem fechada"
        SEAL = "08-lacre", "8 · Lacre ou selo de segurança"
        LOADED = "09-carregado", "9 · Item acomodado no veículo"
        PLATE = "10-placa", "10 · Placa do veículo"
        ODOMETER = "11-odometro", "11 · Odômetro no início da corrida"
        HANDOVER = "12-responsavel", "12 · Responsável pela entrega com o item"

    checklist = models.ForeignKey(PickupChecklist, on_delete=models.CASCADE, related_name="photos")
    slot = models.CharField("etapa", max_length=20, choices=Slot.choices)
    image = models.ImageField("foto", upload_to=checklist_photo_path)
    lat = models.FloatField("latitude", null=True, blank=True, validators=LATITUDE_VALIDATORS)
    lng = models.FloatField("longitude", null=True, blank=True, validators=LONGITUDE_VALIDATORS)
    uploaded_at = models.DateTimeField("enviada em", auto_now_add=True)

    class Meta:
        verbose_name = "foto do checklist"
        verbose_name_plural = "fotos do checklist"
        ordering = ["slot"]
        constraints = [models.UniqueConstraint(fields=["checklist", "slot"], name="unique_photo_per_slot")]

    def __str__(self):
        return f"{self.checklist.delivery.code} · {self.get_slot_display()}"
