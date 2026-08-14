"""Jornada completa da operação, do banco zerado ao repasse pago.

Cada passo é feito pela tela, com a conta de quem faria aquilo na vida real, e
confere no banco se o registro ficou salvo do jeito certo.
"""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from core.defaults import MASTER_EMAIL, MASTER_PASSWORD
from core.models import Notification
from finance.models import DriverPayout, Invoice, PricingPolicy
from operations.models import ChecklistPhoto, Delivery, DeliveryEvent, Driver, PickupChecklist, Vehicle
from operations.tests import driver_payload, fake_document, fake_photo, vehicle_payload

MEDIA_FOR_TESTS = tempfile.mkdtemp(prefix="camboriu-jornada-")

SENHA_EMPRESA = "Padaria@2026"
SENHA_ENTREGADOR = "Entrega@2026"
SENHA_CENTRAL = "Central@2026"
LINHA_DIGITAVEL = "34191790010104351004791020150008912340000012345"

SEM_DESTINOS_EXTRAS = {
    "stops-TOTAL_FORMS": "0", "stops-INITIAL_FORMS": "0",
    "stops-MIN_NUM_FORMS": "0", "stops-MAX_NUM_FORMS": "9",
}


def empresa_payload(**extra):
    payload = {
        "name": "Padaria do Porto", "legal_name": "Padaria do Porto LTDA",
        "document_type": Company.DocumentType.CNPJ, "document": "44555666000181",
        "state_registration": "ISENTO", "municipal_registration": "",
        "tax_regime": Company.TaxRegime.SIMPLES, "business_area": "Panificação",
        "founded_on": "2018-02-01", "email": "contato@padaria.local", "phone": "(47) 3300-1234",
        "contact_name": "Rita Souza", "contact_document": "987.654.321-00", "contact_role": "Sócia",
        "zip_code": "88330-100", "address": "Rua 1500, 200", "complement": "Loja 2",
        "district": "Centro", "city": "Balneário Camboriú", "state": "SC",
        "billing_email": "financeiro@padaria.local", "billing_phone": "(47) 3300-4321",
        "invoice_due_day": "15", "is_active": "on", "notes": "Cliente da integração.",
    }
    payload.update(extra)
    return payload


def cadastro_da_empresa(**extra):
    """O que a própria empresa preenche, com os quatro anexos obrigatórios."""
    payload = empresa_payload(
        document_file=fake_document("cartao-cnpj.pdf"),
        articles_of_association=fake_document("contrato-social.pdf"),
        address_proof=fake_document("comprovante.pdf"),
        contact_document_file=fake_photo("rg.jpg"),
    )
    for interno in ("is_active", "notes"):
        payload.pop(interno)
    payload.update(extra)
    return payload


def checklist_payload():
    dados = {
        "handover_name": "Rita Souza", "handover_document": "987.654.321-00",
        "package_count": 2, "seal_number": "LC-8842",
        "identity_checked": "on", "item_matches_request": "on", "packaging_intact": "on",
        "seal_applied": "on", "documents_checked": "on", "photos_are_original": "on",
        "notes": "Conferido na recepção.", "lat": "-26.9906", "lng": "-48.6349", "accuracy": "8",
    }
    for slot, _ in ChecklistPhoto.Slot.choices:
        dados[f"photo_{slot}"] = fake_photo(f"{slot}.jpg")
    return dados


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class JornadaCompletaTests(TestCase):
    """Do banco zerado até o repasse pago, passando por todas as contas."""

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_FOR_TESTS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        call_command("reset_operation", yes=True, stdout=StringIO())
        self.plataforma = Company.objects.platform()

    # --- utilidades ---

    def entrar(self, usuario, senha, destino):
        self.client.logout()
        resposta = self.client.post(reverse("login"), {"username": usuario, "password": senha})
        self.assertRedirects(
            resposta, reverse(destino), fetch_redirect_response=False, msg_prefix=f"login de {usuario}",
        )

    def abrir(self, nome, *args):
        resposta = self.client.get(reverse(nome, args=args))
        self.assertEqual(resposta.status_code, 200, f"{nome} não abriu")
        return resposta

    def pdf(self, nome, *args):
        resposta = self.abrir(nome, *args)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        conteudo = b"".join(resposta.streaming_content)
        self.assertTrue(conteudo.startswith(b"%PDF"), f"{nome} não gerou PDF")
        return conteudo

    # --- passos da jornada ---

    def test_operacao_completa_do_banco_zerado_ao_repasse_pago(self):
        self.passo_1_banco_zerado()
        empresa = self.passo_2_master_cadastra_a_empresa()
        dono = self.passo_3_master_cria_o_primeiro_acesso(empresa)
        self.passo_4_empresa_conclui_o_cadastro(empresa, dono)
        central = self.passo_5_master_monta_a_equipe_interna()
        entregador, moto = self.passo_6_master_cadastra_entregador_e_frota()
        entrega = self.passo_7_empresa_pede_a_retirada(empresa)
        self.passo_8_central_aciona_o_entregador(entrega, entregador, moto, central)
        self.passo_9_entregador_executa_a_corrida(entrega, entregador)
        self.passo_10_empresa_acompanha_e_baixa_os_documentos(entrega)
        fatura = self.passo_11_empresa_fatura_e_master_emite_o_boleto(empresa, entrega)
        self.passo_12_master_fecha_e_paga_o_repasse(entregador, entrega)
        self.passo_13_conferencia_final(empresa, entrega, fatura, entregador)

    def passo_1_banco_zerado(self):
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(Company.objects.count(), 1)
        self.assertFalse(Driver.objects.exists())
        self.assertFalse(Delivery.objects.exists())
        self.entrar(MASTER_EMAIL, MASTER_PASSWORD, "platform_home")
        self.abrir("platform_home")
        self.abrir("dispatch_board")
        self.abrir("finance_dashboard")
        self.abrir("platform_integration")
        self.pdf("platform_integration_pdf")

    def passo_2_master_cadastra_a_empresa(self):
        resposta = self.client.post(reverse("company_create"), empresa_payload())
        empresa = Company.objects.get(document="44.555.666/0001-81")
        self.assertRedirects(resposta, reverse("company_user_create", args=[empresa.pk]))
        self.assertEqual(empresa.slug, "padaria-do-porto")
        self.assertEqual(empresa.invoice_due_day, 15)
        self.assertTrue(empresa.can_invoice)
        self.assertFalse(empresa.is_registered)

        self.client.post(reverse("company_edit", args=[empresa.pk]), empresa_payload(business_area="Panificação e confeitaria"))
        empresa.refresh_from_db()
        self.assertEqual(empresa.business_area, "Panificação e confeitaria")
        return empresa

    def passo_3_master_cria_o_primeiro_acesso(self, empresa):
        self.client.post(reverse("company_user_create", args=[empresa.pk]), {
            "email": "Rita@Padaria.local", "first_name": "Rita", "last_name": "Souza",
            "role": User.Role.OWNER, "is_active": "on",
            "password1": SENHA_EMPRESA, "password2": SENHA_EMPRESA,
        })
        dono = User.objects.get(username="rita@padaria.local")
        self.assertEqual((dono.company, dono.role), (empresa, User.Role.OWNER))

        self.client.post(reverse("company_user_create", args=[empresa.pk]), {
            "email": "conferente@padaria.local", "first_name": "Caio", "last_name": "Alves",
            "role": User.Role.VIEWER, "is_active": "on",
            "password1": SENHA_EMPRESA, "password2": SENHA_EMPRESA,
        })
        self.assertEqual(empresa.users.count(), 2)
        return dono

    def passo_4_empresa_conclui_o_cadastro(self, empresa, dono):
        self.entrar(dono.username, SENHA_EMPRESA, "dashboard")
        # Sem o cadastro concluído o painel inteiro cai na tela de cadastro.
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("company_profile"))
        self.assertRedirects(self.client.get(reverse("delivery_create")), reverse("company_profile"))

        resposta = self.client.post(reverse("company_profile"), cadastro_da_empresa())
        self.assertRedirects(resposta, reverse("dashboard"))
        empresa.refresh_from_db()
        self.assertTrue(empresa.is_registered)
        self.assertFalse(empresa.missing_documents)
        self.abrir("dashboard")
        self.abrir("company_billing")
        self.assertEqual(self.client.get(reverse("company_own_document", args=["address_proof"])).status_code, 200)
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.COMPANY_REGISTERED, company=empresa).exists())

    def passo_5_master_monta_a_equipe_interna(self):
        self.entrar(MASTER_EMAIL, MASTER_PASSWORD, "platform_home")
        self.client.post(reverse("platform_team_create"), {
            "email": "central@camboriudelivery.local", "first_name": "Ana", "last_name": "Prado",
            "role": User.Role.DISPATCHER, "is_active": "on",
            "password1": SENHA_CENTRAL, "password2": SENHA_CENTRAL,
        })
        central = User.objects.get(username="central@camboriudelivery.local")
        self.assertEqual(central.role, User.Role.DISPATCHER)
        self.assertEqual(central.company, self.plataforma)

        self.client.post(reverse("platform_team_edit", args=[central.pk]), {
            "email": central.email, "first_name": "Ana Paula", "last_name": "Prado",
            "role": User.Role.DISPATCHER, "is_active": "on",
        })
        central.refresh_from_db()
        self.assertEqual(central.first_name, "Ana Paula")

        self.client.post(reverse("finance_pricing"), {
            "base_price": "28.00", "price_per_extra_stop": "11.00", "urgent_surcharge": "9.00",
            "critical_surcharge": "18.00", "driver_share_percent": "70.00",
        })
        politica = PricingPolicy.current()
        self.assertEqual(politica.base_price, Decimal("28.00"))
        self.assertEqual(politica.updated_by_id, User.objects.get(username=MASTER_EMAIL).pk)
        return central

    def passo_6_master_cadastra_entregador_e_frota(self):
        self.client.post(reverse("platform_driver_create"), driver_payload(
            email="bruno@camboriudelivery.local", password1=SENHA_ENTREGADOR, password2=SENHA_ENTREGADOR,
        ))
        entregador = Driver.objects.get(cpf="321.654.987-91")
        self.assertEqual(entregador.company, self.plataforma)
        self.assertEqual(entregador.user.role, User.Role.DRIVER)
        self.assertFalse(entregador.missing_documents)

        moto = self.cadastrar_veiculo(Vehicle.Kind.MOTORCYCLE, "MOT1A23", top_case_liters=90, capacity_kg="30")
        carro = self.cadastrar_veiculo(Vehicle.Kind.CAR, "CAR2B34", doors=4)
        utilitario = self.cadastrar_veiculo(
            Vehicle.Kind.UTILITY, "UTI3C45", doors=3, body_type=Vehicle.Body.BOX,
            gross_weight_kg="3500", cargo_length_cm=250, cargo_width_cm=160, cargo_height_cm=180,
            photo_cargo=fake_photo(),
        )
        self.assertEqual(Vehicle.objects.filter(company=self.plataforma).count(), 3)
        self.assertEqual(utilitario.cargo_volume_liters, 7200)
        self.assertEqual(carro.doors, 4)
        return entregador, moto

    def cadastrar_veiculo(self, tipo, placa, **extra):
        payload = vehicle_payload(kind=tipo, plate=placa, owner_name="Camboriú Delivery", **extra)
        if tipo == Vehicle.Kind.MOTORCYCLE:
            for campo in ("insurer", "insurance_policy", "insurance_expires_at", "insurance_document", "doors"):
                payload.pop(campo, None)
        resposta = self.client.post(reverse("vehicle_create"), payload)
        self.assertRedirects(resposta, reverse("vehicle_list"), msg_prefix=f"veículo {tipo}")
        return Vehicle.objects.get(plate=placa)

    def passo_7_empresa_pede_a_retirada(self, empresa):
        self.entrar("rita@padaria.local", SENHA_EMPRESA, "dashboard")
        politica = PricingPolicy.current()
        resposta = self.client.post(reverse("delivery_create"), {
            "requester": "Confeitaria Central", "item_type": Delivery.ItemType.OTHER,
            "description": "Bolo de três andares", "declared_value": "480.00", "confidential": "",
            "pickup_address": "Rua 1500, 200 · Centro", "pickup_contact": "Rita (47) 3300-1234",
            "pickup_lat": "-26.9906", "pickup_lng": "-48.6349",
            "delivery_address": "Av. Atlântica, 3000", "delivery_contact": "Portaria",
            "delivery_lat": "-26.9950", "delivery_lng": "-48.6300",
            "priority": Delivery.Priority.URGENT, "notes": "Levar com cuidado.",
            "stops-TOTAL_FORMS": "3", "stops-INITIAL_FORMS": "0",
            "stops-MIN_NUM_FORMS": "0", "stops-MAX_NUM_FORMS": "9",
            "stops-0-address": "Rua 3000, 45", "stops-0-contact": "Recepção", "stops-0-notes": "Segundo ponto",
            "stops-1-address": "Rua 4000, 12", "stops-1-contact": "Zeladoria", "stops-1-notes": "",
            "stops-2-address": "", "stops-2-contact": "", "stops-2-notes": "",
        })
        entrega = Delivery.objects.get(requester="Confeitaria Central")
        self.assertRedirects(resposta, reverse("delivery_detail", args=[entrega.pk]))
        self.assertEqual(entrega.company, empresa)
        self.assertEqual(entrega.status, Delivery.Status.REQUESTED)
        self.assertEqual(entrega.destination_count, 3)
        self.assertEqual(entrega.price, politica.base_price + politica.price_per_extra_stop * 2 + politica.urgent_surcharge)
        self.assertEqual(entrega.driver_payout_amount, politica.driver_share(entrega.price))
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.DELIVERY_REQUEST, company=empresa).exists())

        self.client.post(reverse("delivery_edit", args=[entrega.pk]), {
            "requester": "Confeitaria Central", "item_type": Delivery.ItemType.OTHER,
            "description": "Bolo de três andares", "declared_value": "520.00", "confidential": "on",
            "pickup_address": "Rua 1500, 200 · Centro", "pickup_contact": "Rita (47) 3300-1234",
            "delivery_address": "Av. Atlântica, 3000", "delivery_contact": "Portaria",
            "priority": Delivery.Priority.URGENT, "notes": "Levar com cuidado.",
            "stops-TOTAL_FORMS": "0", "stops-INITIAL_FORMS": "0",
            "stops-MIN_NUM_FORMS": "0", "stops-MAX_NUM_FORMS": "9",
        })
        entrega.refresh_from_db()
        self.assertEqual(entrega.declared_value, Decimal("520.00"))
        self.assertTrue(entrega.confidential)
        return entrega

    def passo_8_central_aciona_o_entregador(self, entrega, entregador, moto, central):
        self.entrar(central.username, SENHA_CENTRAL, "platform_home")
        quadro = self.abrir("dispatch_board")
        self.assertContains(quadro, entrega.code)

        resposta = self.client.post(reverse("dispatch_delivery", args=[entrega.pk]), {
            "driver": entregador.pk, "vehicle": moto.pk,
        })
        self.assertRedirects(resposta, reverse("dispatch_detail", args=[entrega.pk]))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.DISPATCHING)
        self.assertEqual((entrega.driver, entrega.vehicle), (entregador, moto))
        self.assertIsNotNone(entrega.dispatched_at)
        self.pdf("delivery_document", entrega.pk)

    def passo_9_entregador_executa_a_corrida(self, entrega, entregador):
        self.entrar(entregador.user.username, SENHA_ENTREGADOR, "driver_home")
        painel = self.abrir("driver_home")
        self.assertContains(painel, entrega.code)
        self.abrir("driver_jobs")
        self.abrir("driver_profile")
        self.abrir("driver_job_detail", entrega.pk)

        self.client.post(reverse("driver_accept_job", args=[entrega.pk]))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.ACCEPTED)
        self.assertIsNotNone(entrega.accepted_at)

        self.client.post(reverse("driver_start_pickup", args=[entrega.pk]))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.PICKUP)

        posicao = self.client.post(
            reverse("driver_ping", args=[entrega.pk]),
            {"lat": -26.9906, "lng": -48.6349, "accuracy": 7.5}, content_type="application/json",
        )
        self.assertEqual(posicao.status_code, 200)

        self.abrir("driver_checklist", entrega.pk)
        resposta = self.client.post(reverse("driver_checklist", args=[entrega.pk]), checklist_payload())
        self.assertRedirects(resposta, reverse("driver_job_detail", args=[entrega.pk]))
        checklist = PickupChecklist.objects.get(delivery=entrega)
        self.assertEqual(checklist.photos.count(), 12)
        self.assertEqual(checklist.missing_photo_slots, [])
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.IN_TRANSIT)
        self.assertIsNotNone(entrega.picked_up_at)

        self.abrir("driver_complete_job", entrega.pk)
        resposta = self.client.post(reverse("driver_complete_job", args=[entrega.pk]), {
            "receiver": "Portaria · Sr. Anselmo", "proof": "RG 3.998.221", "notes": "Entregue na recepção.",
        })
        self.assertRedirects(resposta, reverse("driver_home"))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.DELIVERED)
        self.assertEqual(entrega.receiver, "Portaria · Sr. Anselmo")
        self.assertIsNotNone(entrega.delivered_at)
        self.abrir("driver_history")

    def passo_10_empresa_acompanha_e_baixa_os_documentos(self, entrega):
        self.entrar("rita@padaria.local", SENHA_EMPRESA, "dashboard")
        self.abrir("delivery_list")
        self.abrir("delivery_detail", entrega.pk)
        self.abrir("delivery_tracking", entrega.pk)
        dados = self.client.get(reverse("delivery_tracking_data", args=[entrega.pk])).json()
        self.assertFalse(dados["trackable"], "entrega concluída não publica mais a posição")
        self.assertTrue(dados["checklist_done"])

        termo = self.abrir("delivery_checklist", entrega.pk)
        self.assertContains(termo, "LC-8842")
        foto = ChecklistPhoto.objects.filter(checklist__delivery=entrega).first()
        self.assertEqual(self.client.get(reverse("checklist_photo", args=[entrega.pk, foto.pk])).status_code, 200)
        self.pdf("company_delivery_document", entrega.pk)

    def passo_11_empresa_fatura_e_master_emite_o_boleto(self, empresa, entrega):
        vencimento = timezone.localdate() + timedelta(days=12)
        self.abrir("company_invoice_request")
        resposta = self.client.post(reverse("company_invoice_request"), {
            "due_date": vencimento.isoformat(), "deliveries": [entrega.pk], "notes": "Fechamento da semana",
        })
        fatura = Invoice.objects.get(company=empresa)
        self.assertRedirects(resposta, reverse("company_invoice_detail", args=[fatura.pk]))
        self.assertEqual(fatura.total, entrega.price)
        self.assertEqual(fatura.due_date, vencimento)
        self.assertEqual(fatura.kind, Invoice.Kind.BANK_SLIP)
        self.pdf("company_invoice_document", fatura.pk)

        self.entrar(MASTER_EMAIL, MASTER_PASSWORD, "platform_home")
        self.client.post(reverse("invoice_bank_slip", args=[fatura.pk]), {
            "due_date": vencimento.isoformat(), "bank_slip_line": LINHA_DIGITAVEL,
            "bank_slip_url": "https://banco.local/boleto/1", "notes": "Emitido no banco.",
        })
        fatura.refresh_from_db()
        self.assertEqual(fatura.status, Invoice.Status.ISSUED)
        self.assertIsNotNone(fatura.issued_at)
        self.pdf("invoice_document", fatura.pk)

        self.client.post(reverse("invoice_pay", args=[fatura.pk]), {
            "method": "Boleto", "paid_on": timezone.localdate().isoformat(),
        })
        fatura.refresh_from_db()
        self.assertEqual(fatura.status, Invoice.Status.PAID)
        self.assertIsNotNone(fatura.paid_at)
        return fatura

    def passo_12_master_fecha_e_paga_o_repasse(self, entregador, entrega):
        hoje = timezone.localdate()
        resposta = self.client.post(reverse("payout_create"), {
            "driver": entregador.pk, "reference_start": hoje.replace(day=1).isoformat(),
            "reference_end": hoje.isoformat(),
        })
        repasse = DriverPayout.objects.get(driver=entregador)
        self.assertRedirects(resposta, reverse("payout_detail", args=[repasse.pk]))
        self.assertEqual(repasse.total, entrega.driver_payout_amount)
        self.assertEqual(repasse.rides, 1)

        self.client.post(reverse("payout_pay", args=[repasse.pk]), {"method": "Pix", "paid_on": hoje.isoformat()})
        repasse.refresh_from_db()
        self.assertEqual(repasse.status, DriverPayout.Status.PAID)

        self.abrir("payout_list")
        self.abrir("notification_list")
        self.client.post(reverse("notifications_read"))
        self.assertFalse(Notification.objects.unread().exists())

    def passo_13_conferencia_final(self, empresa, entrega, fatura, entregador):
        painel = self.abrir("finance_dashboard")
        self.assertContains(painel, empresa.name)
        self.abrir("company_detail", empresa.pk)
        self.abrir("platform_deliveries")
        self.abrir("invoice_list")

        entrega.refresh_from_db()
        self.assertEqual(entrega.invoice_id, fatura.pk)
        self.assertIsNotNone(entrega.payout_id)
        self.assertTrue(DeliveryEvent.objects.filter(delivery=entrega).count() >= 6)

        self.entrar(entregador.user.username, SENHA_ENTREGADOR, "driver_home")
        historico = self.abrir("driver_history")
        self.assertContains(historico, str(entrega.driver_payout_amount).replace(".", ","))

        self.entrar("rita@padaria.local", SENHA_EMPRESA, "dashboard")
        extrato = self.abrir("company_billing")
        self.assertContains(extrato, fatura.number)


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class AdministracaoDeContasTests(TestCase):
    """Situações que o admin master resolve depois que a operação já está rodando."""

    def setUp(self):
        call_command("reset_operation", yes=True, stdout=StringIO())
        self.plataforma = Company.objects.platform()
        self.master = User.objects.get(username=MASTER_EMAIL)
        self.client.force_login(self.master)
        self.client.post(reverse("company_create"), empresa_payload())
        self.empresa = Company.objects.get(document="44.555.666/0001-81")
        self.client.post(reverse("company_user_create", args=[self.empresa.pk]), {
            "email": "rita@padaria.local", "first_name": "Rita", "last_name": "Souza",
            "role": User.Role.OWNER, "is_active": "on",
            "password1": SENHA_EMPRESA, "password2": SENHA_EMPRESA,
        })
        self.dono = User.objects.get(username="rita@padaria.local")

    def test_master_redefine_a_senha_de_um_acesso(self):
        nova = "Padaria@Nova2026"
        resposta = self.client.post(reverse("user_password", args=[self.dono.pk]), {
            "password1": nova, "password2": nova,
        })
        self.assertRedirects(resposta, reverse("company_detail", args=[self.empresa.pk]))
        self.client.logout()
        self.assertTrue(self.client.login(username=self.dono.username, password=nova))

    def test_senha_fraca_e_recusada(self):
        resposta = self.client.post(reverse("user_password", args=[self.dono.pk]), {
            "password1": "123456", "password2": "123456",
        })
        self.assertEqual(resposta.status_code, 200)
        self.client.logout()
        self.assertFalse(self.client.login(username=self.dono.username, password="123456"))

    def test_suspender_e_reativar_a_empresa_controla_o_login(self):
        self.client.post(reverse("company_toggle", args=[self.empresa.pk]), {"confirm": "1"})
        self.empresa.refresh_from_db()
        self.assertFalse(self.empresa.is_active)

        self.client.logout()
        recusado = self.client.post(reverse("login"), {"username": self.dono.username, "password": SENHA_EMPRESA})
        self.assertContains(recusado, "suspenso")
        self.assertNotIn("_auth_user_id", self.client.session)

        self.client.force_login(self.master)
        self.client.post(reverse("company_toggle", args=[self.empresa.pk]), {"confirm": "1"})
        self.empresa.refresh_from_db()
        self.assertTrue(self.empresa.is_active)
        self.client.logout()
        self.assertTrue(self.client.login(username=self.dono.username, password=SENHA_EMPRESA))

    def test_desativar_o_acesso_impede_o_login_sem_apagar_o_historico(self):
        self.client.post(reverse("company_user_edit", args=[self.empresa.pk, self.dono.pk]), {
            "email": self.dono.email, "first_name": "Rita", "last_name": "Souza", "role": User.Role.OWNER,
        })
        self.dono.refresh_from_db()
        self.assertFalse(self.dono.is_active)
        self.client.logout()
        self.assertFalse(self.client.login(username=self.dono.username, password=SENHA_EMPRESA))
        self.assertTrue(User.objects.filter(pk=self.dono.pk).exists())

    def test_email_repetido_e_recusado_no_cadastro_de_acesso(self):
        resposta = self.client.post(reverse("company_user_create", args=[self.empresa.pk]), {
            "email": "rita@padaria.local", "first_name": "Outra", "last_name": "Pessoa",
            "role": User.Role.ADMIN, "is_active": "on",
            "password1": SENHA_EMPRESA, "password2": SENHA_EMPRESA,
        })
        self.assertContains(resposta, "Já existe um usuário com este e-mail")
        self.assertEqual(User.objects.filter(username="rita@padaria.local").count(), 1)

    def test_cnpj_repetido_e_recusado_no_cadastro_de_empresa(self):
        resposta = self.client.post(reverse("company_create"), empresa_payload(name="Outra Padaria"))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(Company.objects.clients().count(), 1)

    def test_solicitacao_de_empresa_nao_pode_ser_apagada(self):
        from django.db.models.deletion import ProtectedError

        entrega = Delivery.objects.create(
            company=self.empresa, requester="Cliente", item_type=Delivery.ItemType.DOCUMENT,
            description="Documento", pickup_address="A", pickup_contact="A",
            delivery_address="B", delivery_contact="B",
        )
        with self.assertRaises(ProtectedError):
            entrega.delete()
        with self.assertRaises(ProtectedError):
            Delivery.objects.all().delete()
        self.assertTrue(Delivery.objects.filter(pk=entrega.pk).exists())

    def test_central_cancela_a_solicitacao_com_dupla_confirmacao(self):
        entrega = Delivery.objects.create(
            company=self.empresa, requester="Cliente", item_type=Delivery.ItemType.DOCUMENT,
            description="Documento", pickup_address="A", pickup_contact="A",
            delivery_address="B", delivery_contact="B",
        )
        self.client.post(reverse("dispatch_cancel", args=[entrega.pk]), {"reason": "cliente desistiu"})
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.REQUESTED)

        self.client.post(reverse("dispatch_cancel", args=[entrega.pk]), {"reason": "cliente desistiu", "confirm": "1"})
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.CANCELED)
        self.assertTrue(DeliveryEvent.objects.filter(delivery=entrega, description__icontains="cliente desistiu").exists())
