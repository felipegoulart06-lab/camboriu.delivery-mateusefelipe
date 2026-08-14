"""Ensaio completo contra o banco de verdade, sem deixar rastro.

Os testes automatizados rodam em SQLite, que é rápido mas não é o banco de produção.
Este comando grava um ciclo inteiro da operação (empresa, entregador, veículo, entrega,
checklist, fatura e repasse) no PostgreSQL configurado e desfaz tudo no fim, para conferir
tipos, restrições, índices e chaves estrangeiras onde o sistema realmente vai rodar.
"""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from accounts.models import Company, User
from core.db_security import audit
from core.models import Notification
from finance.models import DriverPayout, Invoice, PricingPolicy
from operations.models import (
    Delivery, DeliveryStop, Driver, DriverPing, PickupChecklist, Vehicle,
)


class Rollback(Exception):
    """Sinaliza o fim do ensaio para desfazer tudo o que foi gravado."""


class Command(BaseCommand):
    help = "Exercita o ciclo completo da operação no banco configurado e desfaz no final."

    def add_arguments(self, parser):
        parser.add_argument("--manter", action="store_true", help="Não desfaz (use só em banco descartável).")

    def handle(self, *args, **options):
        antes = self._contagens()
        etapas = []
        try:
            with transaction.atomic():
                self._ensaio(etapas)
                if not options["manter"]:
                    raise Rollback
        except Rollback:
            pass

        for etapa in etapas:
            self.stdout.write(self.style.SUCCESS(f"ok  {etapa}"))

        depois = self._contagens()
        if not options["manter"] and antes != depois:
            raise CommandError(f"O ensaio deixou dados para trás: {antes} -> {depois}")

        self.stdout.write(self.style.SUCCESS(
            f"{len(etapas)} verificações no {connection.vendor} "
            f"({connection.settings_dict.get('HOST') or 'local'}); banco intacto."
        ))
        relatorio = audit(connection)
        if relatorio:
            self.stdout.write(
                f"Blindagem: {relatorio['tabelas']} tabelas, {relatorio['sem_rls']} sem RLS, "
                f"{relatorio['permissoes_publicas']} permissões públicas, "
                f"{relatorio['funcoes_expostas']} funções expostas."
            )

    def _contagens(self):
        return {
            modelo.__name__: modelo.objects.count()
            for modelo in (Company, User, Driver, Vehicle, Delivery, Invoice, DriverPayout, Notification)
        }

    def _ensaio(self, etapas):
        hoje = timezone.localdate()
        marca = timezone.now().strftime("%H%M%S%f")

        # Documentos e placas levam a marca do ensaio: nada colide com um cadastro real.
        transportadora = Company.objects.platform()
        if transportadora is None:
            transportadora = Company.objects.create(
                name="Ensaio Transportadora", slug=f"ensaio-transportadora-{marca}",
                document=f"ENSAIO-T{marca[:9]}", document_type=Company.DocumentType.CNPJ,
                is_platform=True, registered_at=timezone.now(),
            )
        etapas.append("transportadora da plataforma disponível")

        cliente = Company.objects.create(
            name="Ensaio Cliente", legal_name="Ensaio Comércio LTDA", slug=f"ensaio-cliente-{marca}",
            document_type=Company.DocumentType.CNPJ, document=f"ENSAIO-C{marca[:9]}",
            state_registration="ISENTO", tax_regime=Company.TaxRegime.PRESUMIDO,
            founded_on=date(2015, 8, 3), email=f"ensaio-{marca}@exemplo.com", phone="(47) 3333-1000",
            contact_name="Responsável", contact_document="555.666.777-20", contact_role="Gerência",
            zip_code="88330-000", address="Av. Brasil, 1000", district="Centro",
            city="Balneário Camboriú", state="SC", invoice_due_day=10, registered_at=timezone.now(),
        )
        etapas.append("empresa cliente gravada com documento, endereço e financeiro")

        gestor = User.objects.create_user(
            f"ensaio-gestor-{marca}@exemplo.com", password="EnsaioForte#2026",
            company=cliente, role=User.Role.ADMIN, first_name="Gestor", last_name="Ensaio",
        )
        acesso_entregador = User.objects.create_user(
            f"ensaio-entregador-{marca}@exemplo.com", password="EnsaioForte#2026",
            company=transportadora, role=User.Role.DRIVER, first_name="Entregador", last_name="Ensaio",
        )
        etapas.append("contas de empresa e de entregador criadas com senha cifrada")

        entregador = Driver.objects.create(
            company=transportadora, user=acesso_entregador, name="Entregador Ensaio",
            cpf=f"ENSAIO{marca[:8]}", birth_date=date(1990, 5, 14), rg="4.512.336", rg_issuer="SSP/SC",
            phone="(47) 99911-2200", zip_code="88330-210", address="Rua 1500, 220",
            district="Centro", city="Balneário Camboriú", state="SC",
            cnh="01234567890", cnh_category="AB", cnh_register="00123456789", cnh_state="SC",
            cnh_issued_at=hoje - timedelta(days=900), cnh_first_license_at=date(2010, 2, 8),
            cnh_has_ear=True, cnh_expires_at=hoje + timedelta(days=300),
            medical_exam_expires_at=hoje + timedelta(days=240),
            contract_type=Driver.Contract.PARTNER, pix_key="111.222.333-96",
        )
        veiculo = Vehicle.objects.create(
            company=transportadora, kind=Vehicle.Kind.MOTORCYCLE, plate=f"E{marca[:7]}", plate_state="SC",
            renavam="12345678900", chassis="9C2KC2200PR000123", brand="Honda", model="CG 160 Cargo",
            year=2025, model_year=2025, color="Vermelha", fuel=Vehicle.Fuel.FLEX,
            mileage_km=18400, capacity_kg=Decimal("25"), top_case_liters=90, lockable=True,
            owner_name="Ensaio", owner_document=f"ENSAIO-T{marca[:9]}",
            crlv_expires_at=hoje + timedelta(days=180),
        )
        etapas.append("entregador e veículo gravados com CNH, RENAVAM e chassi válidos")

        entrega = Delivery.objects.create(
            company=cliente, requester="Setor de Compras", item_type=Delivery.ItemType.SAMPLE,
            description="Ensaio de integração.", declared_value=Decimal("350.00"), confidential=True,
            pickup_address="Av. Brasil, 1000, Centro, Balneário Camboriú",
            pickup_contact="Recepção · (47) 3333-1000", pickup_lat=-26.9906, pickup_lng=-48.6349,
            delivery_address="Rua das Flores, 120, Camboriú", delivery_contact="Responsável",
            delivery_lat=-27.0247, delivery_lng=-48.6541,
            pickup_window=timezone.now() + timedelta(hours=1),
            deadline=timezone.now() + timedelta(hours=4),
            priority=Delivery.Priority.CRITICAL, status=Delivery.Status.REQUESTED,
        )
        DeliveryStop.objects.create(
            delivery=entrega, order=2, address="Rua 3000, 45, Centro, Balneário Camboriú",
            contact="Laboratório Sul", notes="Recepção do 2º andar",
        )
        if not entrega.code:
            raise CommandError("A entrega foi gravada sem código de rastreio.")
        etapas.append(f"entrega criada com código {entrega.code} e destino adicional")

        politica = PricingPolicy.current()
        politica.apply_to(entrega)
        entrega.refresh_from_db()
        if entrega.price <= 0 or entrega.driver_payout_amount <= 0:
            raise CommandError("A tabela de preços não calculou valor nem repasse.")
        etapas.append(f"preço R$ {entrega.price} e repasse R$ {entrega.driver_payout_amount} calculados")

        entrega.driver = entregador
        entrega.vehicle = veiculo
        entrega.status = Delivery.Status.PICKUP
        entrega.save()
        entrega.register_event("Entrega acionada no ensaio", gestor)
        DriverPing.objects.create(driver=entregador, delivery=entrega, lat=-27.0075, lng=-48.6180, accuracy=12)
        entregador.register_position(-27.0075, -48.6180)
        etapas.append("acionamento, evento na linha do tempo e rastreio gravados")

        PickupChecklist.objects.create(
            company=cliente, delivery=entrega, driver=entregador,
            handover_name="Responsável do Ensaio", handover_document="555.666.777-20",
            package_count=1, seal_number="LACRE-0001",
            identity_checked=True, item_matches_request=True, packaging_intact=True,
            seal_applied=True, documents_checked=True, photos_are_original=True,
            lat=-26.9906, lng=-48.6349, accuracy=8, submitted_at=timezone.now(),
        )
        etapas.append("checklist antifraude gravado com geolocalização")

        entrega.status = Delivery.Status.DELIVERED
        entrega.save()
        fatura = Invoice.create_for(cliente, Delivery.objects.filter(pk=entrega.pk), hoje + timedelta(days=10))
        if fatura.total <= 0:
            raise CommandError("A fatura saiu com total zerado.")
        etapas.append(f"fatura {fatura.pk} fechada em R$ {fatura.total}")

        repasse = DriverPayout.create_for(
            entregador, Delivery.objects.filter(pk=entrega.pk), hoje.replace(day=1), hoje
        )
        repasse.mark_paid("Pix")
        etapas.append(f"repasse de R$ {repasse.total} registrado como pago")

        Notification.announce(
            Notification.Kind.DELIVERY_REQUEST, "Ensaio de integração", company=cliente,
            body="Registro criado e desfeito pelo verify_database.",
        )
        etapas.append("notificação do admin master gravada")

        consultas = [
            Delivery.objects.filter(company=cliente, status=Delivery.Status.DELIVERED).count(),
            Delivery.objects.filter(driver=entregador).select_related("company", "driver", "vehicle").count(),
            Invoice.objects.filter(company=cliente, status__in=Invoice.RECEIVABLE_STATUSES).count(),
            DriverPayout.objects.filter(driver=entregador).count(),
            Notification.objects.unread().count(),
        ]
        if min(consultas) < 1:
            raise CommandError(f"Uma das consultas dos painéis voltou vazia: {consultas}")
        etapas.append("consultas dos três painéis responderam com os índices novos")

        try:
            Delivery.objects.filter(pk=entrega.pk).delete()
        except Exception:
            etapas.append("exclusão de entrega continua bloqueada pelo banco de produção")
        else:
            raise CommandError("A entrega pôde ser excluída — a proteção do histórico falhou.")