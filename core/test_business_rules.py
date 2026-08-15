"""Regras que protegem a operação: ordem dos passos, ação repetida e dado de outra empresa.

São as tentativas que acontecem no dia a dia — dois cliques no mesmo botão, corrida
aceita fora de hora, fatura paga que alguém tenta cancelar — e que não podem passar.
"""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from finance.models import DriverPayout, Invoice
from operations.models import ChecklistPhoto, Delivery, Driver, PickupChecklist, Vehicle
from operations.tests import fake_photo

MEDIA_FOR_TESTS = tempfile.mkdtemp(prefix="camboriu-regras-")


def foto_pesada(nome="grande.jpg"):
    """Foto de celular moderno: ruído aleatório não comprime, então passa de 1 MB."""
    import io
    import os

    from django.core.files.uploadedfile import SimpleUploadedFile
    from PIL import Image

    buffer = io.BytesIO()
    Image.frombytes("RGB", (800, 800), os.urandom(800 * 800 * 3)).save(buffer, format="JPEG", quality=100)
    return SimpleUploadedFile(nome, buffer.getvalue(), content_type="image/jpeg")


def checklist_payload():
    dados = {
        "handover_name": "Recepção", "handover_document": "987.654.321-00",
        "package_count": 1, "seal_number": "LC-1",
        "identity_checked": "on", "item_matches_request": "on", "packaging_intact": "on",
        "seal_applied": "on", "documents_checked": "on", "photos_are_original": "on", "notes": "",
    }
    for slot, _ in ChecklistPhoto.Slot.choices:
        dados[f"photo_{slot}"] = fake_photo(f"{slot}.jpg")
    return dados


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class RegrasDaOperacaoTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_FOR_TESTS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        agora = timezone.now()
        self.plataforma = Company.objects.create(
            name="Camboriú Delivery", slug="plataforma", document="11.222.333/0001-81",
            is_platform=True, registered_at=agora,
        )
        self.alfa = Company.objects.create(
            name="Padaria Alfa", slug="alfa", document="44.555.666/0001-81", registered_at=agora,
        )
        self.beta = Company.objects.create(
            name="Ateliê Beta", slug="beta", document="12.345.678/0001-95", registered_at=agora,
        )
        self.master = User.objects.create_user("master@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.MASTER)
        self.dono_alfa = User.objects.create_user("dono@alfa.local", password="Acesso@2026", company=self.alfa, role=User.Role.OWNER)
        self.dono_beta = User.objects.create_user("dono@beta.local", password="Acesso@2026", company=self.beta, role=User.Role.OWNER)

        self.carlos = self.entregador("carlos@teste.local", "Carlos Mendes", "1")
        self.marina = self.entregador("marina@teste.local", "Marina Rocha", "2")
        self.afastado = self.entregador("folga@teste.local", "Em folga", "3", status=Driver.Status.AWAY)
        self.frota_beta = Driver.objects.create(
            company=self.beta, name="Frota Beta", cpf="4", cnh="4", cnh_category="B",
            phone="(47) 99944-5500", contract_type=Driver.Contract.EMPLOYEE,
        )
        self.moto = Vehicle.objects.create(
            company=self.plataforma, kind=Vehicle.Kind.MOTORCYCLE, plate="CDL1B34",
            brand="Honda", model="CG 160", year=2025,
        )
        self.parada = Vehicle.objects.create(
            company=self.plataforma, kind=Vehicle.Kind.CAR, plate="CDL2C45", brand="Fiat",
            model="Fiorino", year=2020, status=Vehicle.Status.INACTIVE,
        )
        self.entrega = self.nova_entrega(self.alfa)

    def entregador(self, login, nome, documento, status=Driver.Status.ACTIVE):
        usuario = User.objects.create_user(login, password="Acesso@2026", company=self.plataforma, role=User.Role.DRIVER)
        return Driver.objects.create(
            company=self.plataforma, user=usuario, name=nome, cpf=documento, cnh=documento,
            cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE, status=status,
        )

    def nova_entrega(self, empresa, status=Delivery.Status.REQUESTED, motorista=None, preco=None):
        entrega = Delivery.objects.create(
            company=empresa, requester="Cliente", item_type=Delivery.ItemType.DOCUMENT,
            description="Documento", pickup_address="Av. Brasil, 1000", pickup_contact="Recepção",
            delivery_address="Rua das Flores, 10", delivery_contact="Responsável",
            driver=motorista, status=status,
        )
        if preco:
            Delivery.objects.filter(pk=entrega.pk).update(
                price=Decimal(preco), driver_payout_amount=Decimal(preco) * Decimal("0.7"),
            )
            entrega.refresh_from_db()
        return entrega

    # --- central de despacho ---

    def test_entrega_encerrada_nao_volta_para_o_despacho(self):
        self.client.force_login(self.master)
        for situacao in (Delivery.Status.DELIVERED, Delivery.Status.CANCELED):
            with self.subTest(situacao=situacao):
                entrega = self.nova_entrega(self.alfa, status=situacao, motorista=self.carlos)
                resposta = self.client.post(reverse("dispatch_delivery", args=[entrega.pk]), {"driver": self.marina.pk})
                self.assertRedirects(resposta, reverse("dispatch_board"))
                entrega.refresh_from_db()
                self.assertEqual(entrega.status, situacao)
                self.assertEqual(entrega.driver, self.carlos)

    def test_aceite_so_e_confirmado_quando_o_entregador_foi_acionado(self):
        self.client.force_login(self.master)
        resposta = self.client.post(reverse("dispatch_confirm", args=[self.entrega.pk]))
        self.assertRedirects(resposta, reverse("dispatch_delivery", args=[self.entrega.pk]))
        self.entrega.refresh_from_db()
        self.assertEqual(self.entrega.status, Delivery.Status.REQUESTED)

        self.client.post(reverse("dispatch_delivery", args=[self.entrega.pk]), {"driver": self.carlos.pk, "vehicle": self.moto.pk})
        self.client.post(reverse("dispatch_confirm", args=[self.entrega.pk]))
        self.entrega.refresh_from_db()
        self.assertEqual(self.entrega.status, Delivery.Status.ACCEPTED)
        self.assertIsNotNone(self.entrega.master_confirmed_at)

    def test_entregador_de_outra_empresa_ou_afastado_nao_e_acionado(self):
        self.client.force_login(self.master)
        for motorista, motivo in ((self.frota_beta, "frota de outra empresa"), (self.afastado, "fora de operação")):
            with self.subTest(motivo=motivo):
                resposta = self.client.post(reverse("dispatch_delivery", args=[self.entrega.pk]), {"driver": motorista.pk})
                self.assertEqual(resposta.status_code, 200)
                self.entrega.refresh_from_db()
                self.assertIsNone(self.entrega.driver)
                self.assertEqual(self.entrega.status, Delivery.Status.REQUESTED)

    def test_veiculo_inativo_nao_entra_na_corrida(self):
        self.client.force_login(self.master)
        resposta = self.client.post(reverse("dispatch_delivery", args=[self.entrega.pk]), {
            "driver": self.carlos.pk, "vehicle": self.parada.pk,
        })
        self.assertEqual(resposta.status_code, 200)
        self.entrega.refresh_from_db()
        self.assertIsNone(self.entrega.vehicle)

    def test_entrega_encerrada_nao_pode_ser_cancelada_de_novo(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos)
        self.client.force_login(self.master)
        resposta = self.client.post(reverse("dispatch_cancel", args=[entrega.pk]), {"confirm": "1", "reason": "engano"})
        self.assertRedirects(resposta, reverse("dispatch_detail", args=[entrega.pk]))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.DELIVERED)

    # --- painel do entregador ---

    def test_corrida_de_outro_entregador_nao_abre_nem_aceita(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.DISPATCHING, motorista=self.marina)
        self.client.force_login(self.carlos.user)
        for nome in ("driver_job_detail", "driver_checklist", "driver_complete_job"):
            with self.subTest(rota=nome):
                self.assertEqual(self.client.get(reverse(nome, args=[entrega.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("driver_accept_job", args=[entrega.pk])).status_code, 404)
        self.assertEqual(
            self.client.post(
                reverse("driver_ping", args=[entrega.pk]), {"lat": -26.9, "lng": -48.6},
                content_type="application/json",
            ).status_code,
            404,
        )

    def test_aceitar_duas_vezes_nao_muda_o_que_ja_estava_aceito(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.DISPATCHING, motorista=self.carlos)
        self.client.force_login(self.carlos.user)
        self.client.post(reverse("driver_accept_job", args=[entrega.pk]))
        entrega.refresh_from_db()
        primeiro_aceite = entrega.accepted_at

        self.client.post(reverse("driver_accept_job", args=[entrega.pk]))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.ACCEPTED)
        self.assertEqual(entrega.accepted_at, primeiro_aceite)

    def test_coleta_so_comeca_depois_do_aceite(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.DISPATCHING, motorista=self.carlos)
        self.client.force_login(self.carlos.user)
        self.client.post(reverse("driver_start_pickup", args=[entrega.pk]))
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.DISPATCHING)

    def test_checklist_fora_da_coleta_e_recusado(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.DISPATCHING, motorista=self.carlos)
        self.client.force_login(self.carlos.user)
        resposta = self.client.post(reverse("driver_checklist", args=[entrega.pk]), checklist_payload())
        self.assertRedirects(resposta, reverse("driver_job_detail", args=[entrega.pk]))
        self.assertFalse(PickupChecklist.objects.exists())

    def test_checklist_enviado_nao_e_refeito(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.PICKUP, motorista=self.carlos)
        self.client.force_login(self.carlos.user)
        self.client.post(reverse("driver_checklist", args=[entrega.pk]), checklist_payload())
        checklist = PickupChecklist.objects.get(delivery=entrega)
        enviado_em = checklist.submitted_at

        resposta = self.client.post(reverse("driver_checklist", args=[entrega.pk]), checklist_payload())
        self.assertRedirects(resposta, reverse("driver_job_detail", args=[entrega.pk]))
        checklist.refresh_from_db()
        self.assertEqual(checklist.submitted_at, enviado_em)
        self.assertEqual(ChecklistPhoto.objects.filter(checklist=checklist).count(), 12)

    def test_entrega_finalizada_nao_e_finalizada_de_novo(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.PICKUP, motorista=self.carlos)
        self.client.force_login(self.carlos.user)
        self.client.post(reverse("driver_checklist", args=[entrega.pk]), checklist_payload())
        self.client.post(reverse("driver_complete_job", args=[entrega.pk]), {"receiver": "Portaria"})
        entrega.refresh_from_db()
        primeira_entrega = entrega.delivered_at

        self.client.post(reverse("driver_complete_job", args=[entrega.pk]), {"receiver": "Outra pessoa"})
        entrega.refresh_from_db()
        self.assertEqual(entrega.receiver, "Portaria")
        self.assertEqual(entrega.delivered_at, primeira_entrega)

    def test_finalizar_sem_recebedor_nao_conclui(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.PICKUP, motorista=self.carlos)
        self.client.force_login(self.carlos.user)
        self.client.post(reverse("driver_checklist", args=[entrega.pk]), checklist_payload())
        resposta = self.client.post(reverse("driver_complete_job", args=[entrega.pk]), {"receiver": ""})
        self.assertEqual(resposta.status_code, 200)
        entrega.refresh_from_db()
        self.assertEqual(entrega.status, Delivery.Status.IN_TRANSIT)

    def test_foto_pesada_ou_em_formato_errado_nao_fecha_a_coleta(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.PICKUP, motorista=self.carlos)
        self.client.force_login(self.carlos.user)

        pdf_no_lugar_da_foto = checklist_payload()
        pdf_no_lugar_da_foto["photo_01-local"] = SimpleUploadedFile("nota.pdf", b"%PDF-1.4", content_type="application/pdf")
        resposta = self.client.post(reverse("driver_checklist", args=[entrega.pk]), pdf_no_lugar_da_foto)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(PickupChecklist.objects.exists())

        with override_settings(CHECKLIST_MAX_PHOTO_MB=1):
            pesada = checklist_payload()
            pesada["photo_01-local"] = foto_pesada()
            resposta = self.client.post(reverse("driver_checklist", args=[entrega.pk]), pesada)
            self.assertContains(resposta, "no máximo 1 MB")
        self.assertFalse(PickupChecklist.objects.exists())

    def test_viagem_nao_passa_de_dez_destinos(self):
        self.client.force_login(self.dono_alfa)
        payload = {
            "requester": "Distribuidora", "item_type": Delivery.ItemType.DOCUMENT,
            "description": "Rota longa", "declared_value": "0",
            "pickup_address": "Av. Brasil, 1000", "pickup_contact": "Recepção",
            "delivery_address": "Rua 1", "delivery_contact": "Ponto 1", "priority": Delivery.Priority.NORMAL,
            "stops-TOTAL_FORMS": "10", "stops-INITIAL_FORMS": "0",
            "stops-MIN_NUM_FORMS": "0", "stops-MAX_NUM_FORMS": "9",
        }
        for indice in range(10):
            payload[f"stops-{indice}-address"] = f"Rua {indice + 2}"
            payload[f"stops-{indice}-contact"] = f"Ponto {indice + 2}"
            payload[f"stops-{indice}-notes"] = ""
        resposta = self.client.post(reverse("delivery_create"), payload)
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Delivery.objects.filter(requester="Distribuidora").exists())

    # --- faturamento ---

    def test_fatura_paga_nao_aceita_boleto_novo_nem_cancelamento(self):
        entregue = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        fatura = Invoice.create_for(self.alfa, [entregue], timezone.localdate() + timedelta(days=5))
        fatura.mark_paid("Pix")
        self.client.force_login(self.master)

        self.client.post(reverse("invoice_cancel", args=[fatura.pk]), {"confirm": "1"})
        fatura.refresh_from_db()
        self.assertEqual(fatura.status, Invoice.Status.PAID)

        resposta = self.client.get(reverse("invoice_bank_slip", args=[fatura.pk]))
        self.assertRedirects(resposta, reverse("invoice_detail", args=[fatura.pk]))

        self.client.post(reverse("invoice_pay", args=[fatura.pk]), {"method": "Boleto", "paid_on": ""})
        fatura.refresh_from_db()
        self.assertEqual(fatura.payment_method, "Pix")

    def test_fatura_cancelada_libera_as_entregas_e_ainda_imprime(self):
        entregue = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        fatura = Invoice.create_for(self.alfa, [entregue], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.master)
        self.client.post(reverse("invoice_cancel", args=[fatura.pk]), {"confirm": "1"})

        fatura.refresh_from_db()
        entregue.refresh_from_db()
        self.assertEqual(fatura.status, Invoice.Status.CANCELED)
        self.assertEqual(fatura.total, Decimal("0.00"))
        self.assertIsNone(entregue.invoice_id)
        self.assertTrue(entregue.is_billable)

        pdf = self.client.get(reverse("invoice_document", args=[fatura.pk]))
        self.assertTrue(b"".join(pdf.streaming_content).startswith(b"%PDF"))

    def test_empresa_nao_fatura_entrega_de_outra_empresa(self):
        minha = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        alheia = self.nova_entrega(self.beta, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="80.00")
        self.client.force_login(self.dono_alfa)
        resposta = self.client.post(reverse("company_invoice_request"), {
            "due_date": (timezone.localdate() + timedelta(days=10)).isoformat(),
            "deliveries": [minha.pk, alheia.pk], "notes": "",
        })
        self.assertEqual(resposta.status_code, 200)
        self.assertFalse(Invoice.objects.exists())
        alheia.refresh_from_db()
        self.assertIsNone(alheia.invoice_id)

    def test_so_entra_na_fatura_o_que_foi_entregue_e_ainda_nao_foi_cobrado(self):
        entregue = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        em_rota = self.nova_entrega(self.alfa, status=Delivery.Status.IN_TRANSIT, motorista=self.carlos, preco="30.00")
        self.client.force_login(self.dono_alfa)
        disponiveis = self.client.get(reverse("company_invoice_request")).context["available"]
        self.assertIn(entregue, disponiveis)
        self.assertNotIn(em_rota, disponiveis)

        Invoice.create_for(self.alfa, [entregue], timezone.localdate() + timedelta(days=5))
        self.assertRedirects(self.client.get(reverse("company_invoice_request")), reverse("company_billing"))

    def test_entrega_sem_preco_nao_pode_ser_faturada(self):
        sem_preco = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos)
        Delivery.objects.filter(pk=sem_preco.pk).update(price=Decimal("0"))
        sem_preco.refresh_from_db()
        self.assertFalse(sem_preco.is_billable)
        self.client.force_login(self.dono_alfa)
        self.assertRedirects(self.client.get(reverse("company_invoice_request")), reverse("company_billing"))

    # --- repasses ---

    def test_repasse_pago_nao_e_desfeito(self):
        entregue = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        repasse = DriverPayout.create_for(self.carlos, [entregue], timezone.localdate(), timezone.localdate())
        repasse.mark_paid("Pix")
        self.client.force_login(self.master)
        self.client.post(reverse("payout_reopen", args=[repasse.pk]), {"confirm": "1"})
        self.assertTrue(DriverPayout.objects.filter(pk=repasse.pk).exists())
        entregue.refresh_from_db()
        self.assertEqual(entregue.payout_id, repasse.pk)

    def test_periodo_sem_corrida_nao_gera_repasse(self):
        self.client.force_login(self.master)
        ontem = timezone.localdate() - timedelta(days=1)
        resposta = self.client.post(reverse("payout_create"), {
            "driver": self.carlos.pk, "reference_start": ontem.isoformat(), "reference_end": ontem.isoformat(),
        })
        self.assertContains(resposta, "Não há entregas concluídas")
        self.assertFalse(DriverPayout.objects.exists())

    def test_periodo_invertido_e_recusado(self):
        self.client.force_login(self.master)
        hoje = timezone.localdate()
        resposta = self.client.post(reverse("payout_create"), {
            "driver": self.carlos.pk, "reference_start": hoje.isoformat(),
            "reference_end": (hoje - timedelta(days=5)).isoformat(),
        })
        self.assertContains(resposta, "não pode ser anterior")
        self.assertFalse(DriverPayout.objects.exists())

    def test_corrida_ja_repassada_nao_entra_em_outro_repasse(self):
        entregue = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        hoje = timezone.localdate()
        DriverPayout.create_for(self.carlos, [entregue], hoje, hoje)
        self.client.force_login(self.master)
        resposta = self.client.post(reverse("payout_create"), {
            "driver": self.carlos.pk, "reference_start": hoje.replace(day=1).isoformat(), "reference_end": hoje.isoformat(),
        })
        self.assertContains(resposta, "Não há entregas concluídas")
        self.assertEqual(DriverPayout.objects.count(), 1)

    def test_repasse_nao_mistura_corrida_de_outro_entregador(self):
        minha = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        da_marina = self.nova_entrega(self.alfa, status=Delivery.Status.DELIVERED, motorista=self.marina, preco="50.00")
        hoje = timezone.localdate()
        self.client.force_login(self.master)
        self.client.post(reverse("payout_create"), {
            "driver": self.carlos.pk, "reference_start": hoje.replace(day=1).isoformat(), "reference_end": hoje.isoformat(),
        })
        repasse = DriverPayout.objects.get(driver=self.carlos)
        self.assertEqual(list(repasse.deliveries.all()), [minha])
        da_marina.refresh_from_db()
        self.assertIsNone(da_marina.payout_id)

    # --- integridade dos vínculos ---

    def test_entrega_nao_aceita_veiculo_de_outra_empresa(self):
        veiculo_beta = Vehicle.objects.create(
            company=self.beta, kind=Vehicle.Kind.CAR, plate="BET1D23", brand="VW", model="Gol", year=2022,
        )
        self.entrega.vehicle = veiculo_beta
        with self.assertRaises(ValidationError):
            self.entrega.save()

    def test_checklist_precisa_ser_do_entregador_da_corrida(self):
        entrega = self.nova_entrega(self.alfa, status=Delivery.Status.PICKUP, motorista=self.carlos)
        with self.assertRaises(ValidationError):
            PickupChecklist.objects.create(
                company=self.alfa, delivery=entrega, driver=self.marina, handover_name="Recepção",
                handover_document="987.654.321-00", package_count=1, identity_checked=True,
                item_matches_request=True, packaging_intact=True, seal_applied=True,
                documents_checked=True, photos_are_original=True,
            )

    def test_prazo_nao_pode_ser_anterior_a_coleta(self):
        agora = timezone.now()
        self.entrega.pickup_window = agora + timedelta(hours=3)
        self.entrega.deadline = agora + timedelta(hours=1)
        with self.assertRaises(ValidationError):
            self.entrega.save()

    def test_placa_repetida_na_mesma_empresa_e_bloqueada(self):
        from django.db.utils import IntegrityError

        with self.assertRaises(IntegrityError):
            Vehicle.objects.create(
                company=self.plataforma, kind=Vehicle.Kind.MOTORCYCLE, plate=self.moto.plate,
                brand="Honda", model="Biz", year=2024,
            )
