"""Documentos em PDF: solicitação, fatura e manual de integração.

O texto vai para o ReportLab, que lê marcação. Endereço com "<" ou razão social com
"&" precisa sair impresso, e não derrubar o download.
"""
from datetime import timedelta
from decimal import Decimal
import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from finance.models import Invoice
from finance.pdf import brl, delivery_request_pdf, delivery_request_rows, invoice_pdf
from operations.dossier_pdf import company_dossier_pdf, driver_dossier_pdf, vehicle_dossier_pdf
from operations.models import Delivery, DeliveryStop, Driver, Vehicle
from operations.playbook_pdf import integration_pdf
from operations.tests import fake_document, fake_photo

TEXTO_HOSTIL = 'Rua <b> das Flores & Cia, 10 "fundos" <100>'


MEDIA_FOR_TESTS = tempfile.mkdtemp(prefix="camboriu-pdf-")


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class DocumentosEmPdfTests(TestCase):
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
        self.empresa = Company.objects.create(
            name="Silva & Filhos", legal_name='Silva & Filhos <ME> "Matriz"', slug="silva",
            document="44.555.666/0001-81", state_registration="ISENTO",
            address="Av. Brasil & Anexo, 1000", district="Centro", city="Balneário Camboriú",
            state="SC", contact_name="Rita & Cia", phone="(47) 3300-1234", email="rita@silva.local",
            registered_at=agora,
        )
        login = User.objects.create_user("carlos@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.DRIVER)
        self.entregador = Driver.objects.create(
            company=self.plataforma, user=login, name="Carlos <Mendes> & Cia", cpf="1", cnh="1",
            cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE,
        )
        self.veiculo = Vehicle.objects.create(
            company=self.plataforma, kind=Vehicle.Kind.MOTORCYCLE, plate="CDL1B34",
            brand="Honda", model="CG 160", year=2025,
        )
        self.master = User.objects.create_user("master@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.MASTER)

    def entrega(self, **extra):
        dados = {
            "company": self.empresa, "requester": "Confeitaria <Central> & Cia",
            "item_type": Delivery.ItemType.OTHER, "description": TEXTO_HOSTIL,
            "pickup_address": TEXTO_HOSTIL, "pickup_contact": "Rita & Cia",
            "delivery_address": TEXTO_HOSTIL, "delivery_contact": "Portaria <B>",
            "notes": "Observação com <marcação> & símbolos",
        }
        dados.update(extra)
        return Delivery.objects.create(**dados)

    def conteudo(self, buffer):
        dados = buffer.getvalue()
        self.assertTrue(dados.startswith(b"%PDF"))
        self.assertGreater(len(dados), 1000)
        return dados

    def test_solicitacao_com_texto_de_marcacao_gera_o_pdf(self):
        self.conteudo(delivery_request_pdf(self.entrega()))

    def test_solicitacao_sem_entregador_faturamento_ou_checklist(self):
        self.conteudo(delivery_request_pdf(self.entrega()))

    def test_solicitacao_completa_com_nove_destinos(self):
        entrega = self.entrega(
            driver=self.entregador, vehicle=self.veiculo, status=Delivery.Status.DELIVERED,
            priority=Delivery.Priority.CRITICAL, confidential=True, declared_value=Decimal("1500.00"),
            deadline=timezone.now() + timedelta(hours=5),
        )
        for ordem in range(2, 11):
            DeliveryStop.objects.create(
                delivery=entrega, order=ordem, address=f"{TEXTO_HOSTIL} nº {ordem}",
                contact="Recepção & Cia", notes="Deixar com <o> zelador",
            )
        self.assertEqual(entrega.destination_count, 10)
        self.conteudo(delivery_request_pdf(entrega))

    def test_pdf_do_entregador_omite_valor_do_produto_e_da_entrega(self):
        entrega = self.entrega(driver=self.entregador, declared_value=Decimal("1500.00"))
        Delivery.objects.filter(pk=entrega.pk).update(price=Decimal("88.88"))
        entrega.refresh_from_db()
        rotulos_empresa = [label for bloco in delivery_request_rows(entrega) for label, _ in bloco]
        rotulos_motorista = [label for bloco in delivery_request_rows(entrega, hide_values=True) for label, _ in bloco]
        valores_motorista = [valor for bloco in delivery_request_rows(entrega, hide_values=True) for _, valor in bloco]
        self.assertIn("Valor declarado", rotulos_empresa)
        self.assertIn("Valor da entrega", rotulos_empresa)
        self.assertNotIn("Valor declarado", rotulos_motorista)
        self.assertNotIn("Valor da entrega", rotulos_motorista)
        self.assertNotIn("Fatura", rotulos_motorista)
        self.assertNotIn(brl(entrega.declared_value), valores_motorista)
        self.assertNotIn(brl(entrega.price), valores_motorista)
        self.conteudo(delivery_request_pdf(entrega, hide_values=True))

    def test_pdf_da_empresa_mascara_cpf_e_omite_documentos_do_motorista(self):
        self.entregador.cpf = "321.654.987-91"
        self.entregador.cnh = "55544433322"
        self.entregador.save()
        self.veiculo.color = "Vermelho"
        self.veiculo.crlv_expires_at = timezone.localdate() + timedelta(days=90)
        self.veiculo.save()
        entrega = self.entrega(driver=self.entregador, vehicle=self.veiculo)
        texto = " ".join(valor for bloco in delivery_request_rows(entrega, public_fleet=True) for _, valor in bloco)
        self.assertIn("321.6**.***-**", texto)
        self.assertIn("Honda CG 160", texto)
        self.assertIn("CDL1B34", texto)
        self.assertIn("Vermelho", texto)
        self.assertNotIn("321.654.987-91", texto)
        self.assertNotIn("654.987", texto)
        self.assertNotIn("55544433322", texto)
        self.assertNotIn(self.entregador.cnh, texto)
        plataforma = " ".join(valor for bloco in delivery_request_rows(entrega) for _, valor in bloco)
        self.assertIn(self.entregador.name, plataforma)
        self.assertNotIn("321.6**.***-**", plataforma)
        self.conteudo(delivery_request_pdf(entrega, public_fleet=True))

    def test_entregador_baixa_o_pdf_sem_valores(self):
        entrega = self.entrega(driver=self.entregador, declared_value=Decimal("1500.00"))
        Delivery.objects.filter(pk=entrega.pk).update(price=Decimal("88.88"))
        self.client.force_login(self.entregador.user)
        resposta = self.client.get(reverse("driver_job_document", args=[entrega.pk]))
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(resposta.streaming_content).startswith(b"%PDF"))

    def test_fatura_em_boleto_com_linha_digitavel_e_observacoes(self):
        entrega = self.entrega(driver=self.entregador, status=Delivery.Status.DELIVERED)
        Delivery.objects.filter(pk=entrega.pk).update(price=Decimal("30.00"))
        entrega.refresh_from_db()
        fatura = Invoice.create_for(self.empresa, [entrega], timezone.localdate() + timedelta(days=10))
        fatura.bank_slip_line = "34191790010104351004791020150008912340000012345"
        fatura.notes = "Pagamento <em> boleto & Pix"
        fatura.status = Invoice.Status.ISSUED
        fatura.save()
        self.conteudo(invoice_pdf(fatura))

    def test_fatura_em_recibo_de_empresa_com_cpf(self):
        pessoa = Company.objects.create(
            name="Ateliê Beta", slug="beta", document="987.654.321-00",
            document_type=Company.DocumentType.CPF, registered_at=timezone.now(),
        )
        entrega = self.entrega(company=pessoa, driver=self.entregador, status=Delivery.Status.DELIVERED)
        Delivery.objects.filter(pk=entrega.pk).update(price=Decimal("25.00"))
        entrega.refresh_from_db()
        fatura = Invoice.create_for(pessoa, [entrega], timezone.localdate() + timedelta(days=5))
        self.assertEqual(fatura.kind, Invoice.Kind.RECEIPT)
        self.conteudo(invoice_pdf(fatura))

    def test_fatura_sem_entregas_ainda_imprime(self):
        fatura = Invoice.objects.create(company=self.empresa, due_date=timezone.localdate(), total=0)
        self.conteudo(invoice_pdf(fatura))

    def test_manual_de_integracao_sai_completo(self):
        self.conteudo(integration_pdf())

    def test_download_pelas_telas_devolve_arquivo_para_baixar(self):
        entrega = self.entrega(driver=self.entregador, status=Delivery.Status.DELIVERED)
        Delivery.objects.filter(pk=entrega.pk).update(price=Decimal("30.00"))
        entrega.refresh_from_db()
        fatura = Invoice.create_for(self.empresa, [entrega], timezone.localdate() + timedelta(days=5))

        self.client.force_login(self.master)
        for nome, argumentos in (
            ("delivery_document", [entrega.pk]),
            ("invoice_document", [fatura.pk]),
            ("platform_integration_pdf", []),
        ):
            with self.subTest(documento=nome):
                resposta = self.client.get(reverse(nome, args=argumentos))
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta["Content-Type"], "application/pdf")
                self.assertTrue(b"".join(resposta.streaming_content).startswith(b"%PDF"))

    def test_dossie_de_empresa_entregador_e_veiculo_gera_pdf(self):
        self.empresa.notes = TEXTO_HOSTIL
        self.empresa.address_proof = fake_document("comprovante.pdf")
        self.empresa.contact_document_file = fake_photo("rg.jpg")
        self.empresa.save()
        self.entregador.notes = TEXTO_HOSTIL
        self.entregador.portrait = fake_photo("retrato.jpg")
        self.entregador.cnh_front = fake_document("cnh.pdf")
        self.entregador.save()
        self.veiculo.notes = TEXTO_HOSTIL
        self.veiculo.photo_front = fake_photo("frente.jpg")
        self.veiculo.crlv_document = fake_document("crlv.pdf")
        self.veiculo.save()

        self.conteudo(company_dossier_pdf(self.empresa, users=[self.master], include_internal=True))
        self.conteudo(company_dossier_pdf(self.empresa, include_internal=False))
        self.conteudo(driver_dossier_pdf(self.entregador))
        self.conteudo(vehicle_dossier_pdf(self.veiculo))

    def test_dossies_baixam_pelas_telas_de_cadastro(self):
        self.empresa.contact_document_file = fake_photo("rg.jpg")
        self.empresa.save()
        self.entregador.portrait = fake_photo("retrato.jpg")
        self.entregador.save()
        self.veiculo.photo_front = fake_photo("frente.jpg")
        self.veiculo.save()
        dono = User.objects.create_user(
            "rita@silva.local", password="Acesso@2026", company=self.empresa, role=User.Role.OWNER,
        )

        self.client.force_login(self.master)
        for nome, argumentos in (
            ("company_dossier", [self.empresa.pk]),
            ("platform_driver_dossier", [self.entregador.pk]),
            ("vehicle_dossier", [self.veiculo.pk]),
        ):
            with self.subTest(documento=nome):
                resposta = self.client.get(reverse(nome, args=argumentos))
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(resposta["Content-Type"], "application/pdf")
                self.assertTrue(b"".join(resposta.streaming_content).startswith(b"%PDF"))

        self.client.force_login(dono)
        resposta = self.client.get(reverse("company_own_dossier"))
        self.assertEqual(resposta.status_code, 200)
        self.assertTrue(b"".join(resposta.streaming_content).startswith(b"%PDF"))
        self.assertRedirects(self.client.get(reverse("platform_driver_dossier", args=[self.entregador.pk])), reverse("dashboard"))
