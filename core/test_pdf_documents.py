"""Documentos em PDF: solicitação, fatura e manual de integração.

O texto vai para o ReportLab, que lê marcação. Endereço com "<" ou razão social com
"&" precisa sair impresso, e não derrubar o download.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from finance.models import Invoice
from finance.pdf import delivery_request_pdf, invoice_pdf
from operations.models import Delivery, DeliveryStop, Driver, Vehicle
from operations.playbook_pdf import integration_pdf

TEXTO_HOSTIL = 'Rua <b> das Flores & Cia, 10 "fundos" <100>'


class DocumentosEmPdfTests(TestCase):
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
