"""Filtros, buscas e indicadores das telas de operação.

Cada lista do sistema tem filtro ou busca. Aqui elas são exercitadas com dados de
mais de uma empresa, para garantir que filtram de verdade e não vazam registro alheio.
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from core.models import Notification
from finance.models import DriverPayout, Invoice
from operations.models import Delivery, Driver, Vehicle


class TelasDaOperacaoTests(TestCase):
    def setUp(self):
        agora = timezone.now()
        self.plataforma = Company.objects.create(
            name="Camboriú Delivery", slug="plataforma", document="11.222.333/0001-81",
            is_platform=True, registered_at=agora,
        )
        self.alfa = Company.objects.create(
            name="Padaria Alfa", legal_name="Alfa Alimentos LTDA", slug="alfa",
            document="44.555.666/0001-81", city="Balneário Camboriú", state="SC", registered_at=agora,
        )
        self.beta = Company.objects.create(
            name="Ateliê Beta", legal_name="Beatriz Souza", slug="beta", document="987.654.321-00",
            document_type=Company.DocumentType.CPF, city="Camboriú", state="SC", registered_at=agora,
        )
        self.master = User.objects.create_user("master@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.MASTER)
        self.dono_alfa = User.objects.create_user("dono@alfa.local", password="Acesso@2026", company=self.alfa, role=User.Role.OWNER)
        login_carlos = User.objects.create_user("carlos@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.DRIVER)

        self.carlos = Driver.objects.create(
            company=self.plataforma, user=login_carlos, name="Carlos Mendes", cpf="1", cnh="1",
            cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE,
        )
        self.marina = Driver.objects.create(
            company=self.plataforma, name="Marina Rocha", cpf="2", cnh="2", cnh_category="A",
            phone="(47) 99922-3300", contract_type=Driver.Contract.PARTNER,
        )
        self.moto = Vehicle.objects.create(
            company=self.plataforma, kind=Vehicle.Kind.MOTORCYCLE, plate="CDL1B34",
            brand="Honda", model="CG 160", year=2025,
        )

        self.pedida = self.entrega(self.alfa, "Pedido em aberto")
        self.em_rota = self.entrega(self.alfa, "Em trânsito", status=Delivery.Status.IN_TRANSIT, motorista=self.carlos)
        self.entregue = self.entrega(self.alfa, "Concluída", status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="30.00")
        self.da_beta = self.entrega(self.beta, "Pedido da Beta", status=Delivery.Status.DELIVERED, motorista=self.carlos, preco="25.00")

        self.client.force_login(self.master)

    def entrega(self, empresa, solicitante, status=Delivery.Status.REQUESTED, motorista=None, preco=None):
        registro = Delivery.objects.create(
            company=empresa, requester=solicitante, item_type=Delivery.ItemType.DOCUMENT,
            description="Teste", pickup_address="Av. Brasil, 1000", pickup_contact="Recepção",
            delivery_address="Rua das Flores, 10", delivery_contact="Responsável",
            driver=motorista, status=status,
        )
        if preco:
            Delivery.objects.filter(pk=registro.pk).update(
                price=Decimal(preco), driver_payout_amount=Decimal(preco) * Decimal("0.7"),
            )
            registro.refresh_from_db()
        return registro

    # --- listas da central ---

    def test_lista_de_entregas_da_central_filtra_por_status_empresa_e_busca(self):
        url = reverse("platform_deliveries")
        por_status = self.client.get(url, {"status": Delivery.Status.DELIVERED})
        self.assertContains(por_status, self.entregue.code)
        self.assertNotContains(por_status, self.pedida.code)

        por_empresa = self.client.get(url, {"company": self.beta.pk})
        self.assertContains(por_empresa, self.da_beta.code)
        self.assertNotContains(por_empresa, self.pedida.code)

        por_busca = self.client.get(url, {"q": "Em trânsito"})
        self.assertContains(por_busca, self.em_rota.code)
        self.assertNotContains(por_busca, self.entregue.code)

        por_codigo = self.client.get(url, {"q": self.pedida.code})
        self.assertContains(por_codigo, self.pedida.code)

    def test_busca_de_empresas_procura_por_nome_documento_e_cidade(self):
        url = reverse("company_list")
        for termo in ("Padaria", "44.555.666", "Balneário"):
            with self.subTest(busca=termo):
                resposta = self.client.get(url, {"q": termo})
                self.assertContains(resposta, "Padaria Alfa")
                self.assertNotContains(resposta, "Ateliê Beta")

    def test_busca_de_entregadores_procura_por_nome_cpf_e_telefone(self):
        url = reverse("platform_drivers")
        for termo in ("Marina", "99922"):
            with self.subTest(busca=termo):
                resposta = self.client.get(url, {"q": termo})
                self.assertContains(resposta, "Marina Rocha")
                self.assertNotContains(resposta, "Carlos Mendes")

    def test_quadro_de_despacho_separa_o_que_chega_do_que_esta_rodando(self):
        quadro = self.client.get(reverse("dispatch_board"))
        self.assertIn(self.pedida, quadro.context["incoming"])
        self.assertIn(self.em_rota, quadro.context["running"])
        self.assertNotIn(self.entregue, quadro.context["running"])
        # Entregador sem login não pode ser acionado, então nem aparece na lista.
        self.assertIn(self.carlos, quadro.context["available_drivers"])
        self.assertNotIn(self.marina, quadro.context["available_drivers"])

    # --- financeiro ---

    def test_lista_de_faturas_filtra_por_situacao_vencida_e_empresa(self):
        vencida = Invoice.create_for(self.alfa, [self.entregue], timezone.localdate() - timedelta(days=3))
        paga = Invoice.create_for(self.beta, [self.da_beta], timezone.localdate() + timedelta(days=5))
        paga.mark_paid("Pix")

        url = reverse("invoice_list")
        atrasadas = self.client.get(url, {"status": "overdue"})
        self.assertContains(atrasadas, vencida.number)
        self.assertNotContains(atrasadas, paga.number)

        pagas = self.client.get(url, {"status": Invoice.Status.PAID})
        self.assertContains(pagas, paga.number)
        self.assertNotContains(pagas, vencida.number)

        da_beta = self.client.get(url, {"company": self.beta.pk})
        self.assertContains(da_beta, paga.number)
        self.assertNotContains(da_beta, vencida.number)

    def test_painel_contabil_mostra_vencidas_e_desempenho(self):
        Invoice.create_for(self.alfa, [self.entregue], timezone.localdate() - timedelta(days=2))
        painel = self.client.get(reverse("finance_dashboard"))
        self.assertEqual(painel.status_code, 200)
        self.assertEqual(len(painel.context["overdue"]), 1)
        self.assertTrue(any(linha["driver"] == self.carlos for linha in painel.context["drivers"]))
        self.assertTrue(any(linha["company"] == self.alfa for linha in painel.context["companies"]))

    def test_empresa_em_cpf_recebe_recibo_e_nao_boleto(self):
        resposta = self.client.post(reverse("invoice_create", args=[self.beta.pk]), {"deliveries": [self.da_beta.pk]})
        fatura = Invoice.objects.get(company=self.beta)
        self.assertRedirects(resposta, reverse("invoice_detail", args=[fatura.pk]))
        self.assertEqual(fatura.kind, Invoice.Kind.RECEIPT)
        self.assertEqual(fatura.total, Decimal("25.00"))

    def test_ajuste_de_valores_da_entrega_fica_registrado(self):
        resposta = self.client.post(reverse("delivery_price", args=[self.entregue.pk]), {
            "price": "42.00", "driver_payout_amount": "29.40",
        })
        self.assertRedirects(resposta, reverse("dispatch_detail", args=[self.entregue.pk]))
        self.entregue.refresh_from_db()
        self.assertEqual(self.entregue.price, Decimal("42.00"))
        self.assertEqual(self.entregue.driver_payout_amount, Decimal("29.40"))
        self.assertTrue(self.entregue.events.filter(description__icontains="Valores revisados").exists())

    def test_entrega_ja_faturada_nao_tem_o_valor_alterado(self):
        Invoice.create_for(self.alfa, [self.entregue], timezone.localdate() + timedelta(days=5))
        resposta = self.client.post(reverse("delivery_price", args=[self.entregue.pk]), {
            "price": "99.00", "driver_payout_amount": "10.00",
        })
        self.assertRedirects(resposta, reverse("dispatch_detail", args=[self.entregue.pk]))
        self.entregue.refresh_from_db()
        self.assertEqual(self.entregue.price, Decimal("30.00"))

    def test_lista_de_repasses_aponta_quem_tem_corrida_a_fechar(self):
        lista = self.client.get(reverse("payout_list"))
        self.assertIn(self.carlos, lista.context["pending_drivers"])

        DriverPayout.create_for(self.carlos, [self.entregue, self.da_beta], timezone.localdate(), timezone.localdate())
        lista = self.client.get(reverse("payout_list"))
        self.assertNotIn(self.carlos, lista.context["pending_drivers"])

    # --- notificações ---

    def test_notificacoes_filtram_as_nao_lidas(self):
        lida = Notification.announce(Notification.Kind.DELIVERY_REQUEST, "Pedido antigo", company=self.alfa)
        Notification.objects.filter(pk=lida.pk).update(read_at=timezone.now())
        nova = Notification.announce(Notification.Kind.INVOICE_REQUEST, "Fatura nova", company=self.beta)

        todas = self.client.get(reverse("notification_list"))
        self.assertContains(todas, "Pedido antigo")
        self.assertContains(todas, "Fatura nova")

        pendentes = self.client.get(reverse("notification_list"), {"filtro": "nao-lidas"})
        self.assertContains(pendentes, "Fatura nova")
        self.assertNotContains(pendentes, "Pedido antigo")

        self.client.post(reverse("notifications_read"))
        nova.refresh_from_db()
        self.assertIsNotNone(nova.read_at)

    # --- painéis ---

    def test_painel_da_empresa_conta_so_o_que_e_dela(self):
        self.client.force_login(self.dono_alfa)
        painel = self.client.get(reverse("dashboard"))
        self.assertEqual(painel.context["total"], 3)
        self.assertEqual(painel.context["delivered"], 1)
        self.assertEqual(painel.context["fleet_label"], "frota SC Transporte Executivo")
        self.assertNotContains(painel, self.da_beta.code)

    def test_lista_de_entregas_da_empresa_filtra_por_status(self):
        self.client.force_login(self.dono_alfa)
        resposta = self.client.get(reverse("delivery_list"), {"status": Delivery.Status.DELIVERED})
        self.assertContains(resposta, self.entregue.code)
        self.assertNotContains(resposta, self.pedida.code)

    def test_empresa_nao_acessa_cadastro_de_frota(self):
        self.client.force_login(self.dono_alfa)
        painel = self.client.get(reverse("dashboard"))
        self.assertNotContains(painel, reverse("driver_list"))
        self.assertNotContains(painel, reverse("vehicle_list"))
        self.assertRedirects(self.client.get(reverse("driver_list")), reverse("dashboard"))
        self.assertRedirects(self.client.get(reverse("vehicle_list")), reverse("dashboard"))
        self.assertRedirects(self.client.get(reverse("vehicle_create")), reverse("dashboard"))
        self.assertRedirects(self.client.get(reverse("platform_driver_create")), reverse("dashboard"))

    def test_entregador_avisa_a_central_quando_sai_e_quando_volta(self):
        self.client.force_login(self.carlos.user)
        for situacao in (Driver.Status.AWAY, Driver.Status.ACTIVE):
            with self.subTest(situacao=situacao):
                self.client.post(reverse("driver_availability"), {"status": situacao})
                self.carlos.refresh_from_db()
                self.assertEqual(self.carlos.status, situacao)

        self.client.post(reverse("driver_availability"), {"status": "inventado"})
        self.carlos.refresh_from_db()
        self.assertEqual(self.carlos.status, Driver.Status.ACTIVE)

    def test_mapa_avisa_quando_a_posicao_do_entregador_esta_velha(self):
        from django.test import override_settings

        self.carlos.register_position(-26.9906, -48.6349)
        self.client.force_login(self.dono_alfa)
        url = reverse("delivery_tracking_data", args=[self.em_rota.pk])

        recente = self.client.get(url).json()
        self.assertTrue(recente["trackable"])
        self.assertFalse(recente["driver"]["stale"])
        self.assertEqual(len(recente["trail"]), 0)

        with override_settings(TRACKING_STALE_SECONDS=0):
            velha = self.client.get(url).json()
        self.assertTrue(velha["driver"]["stale"])

    def test_posicao_enviada_pelo_celular_aparece_no_rastro(self):
        self.client.force_login(self.carlos.user)
        for latitude in (-26.9906, -26.9910):
            self.client.post(
                reverse("driver_ping", args=[self.em_rota.pk]),
                {"lat": latitude, "lng": -48.6349}, content_type="application/json",
            )
        self.client.force_login(self.dono_alfa)
        dados = self.client.get(reverse("delivery_tracking_data", args=[self.em_rota.pk])).json()
        self.assertEqual(len(dados["trail"]), 2)
        self.assertAlmostEqual(dados["driver"]["lat"], -26.9910)

    def test_posicao_com_corpo_invalido_e_recusada(self):
        self.client.force_login(self.carlos.user)
        url = reverse("driver_ping", args=[self.em_rota.pk])
        for corpo in ("", "{isso não é json}", '{"lat": "aqui"}', '{"lng": -48.6}'):
            with self.subTest(corpo=corpo):
                resposta = self.client.post(url, corpo, content_type="application/json")
                self.assertEqual(resposta.status_code, 400)
        self.assertEqual(self.client.get(url).status_code, 405)

    def test_pagina_publica_apresenta_o_servico_e_o_acesso_ao_painel(self):
        self.client.logout()
        inicio = self.client.get(reverse("landing"))
        self.assertContains(inicio, "transporte executivo")
        self.assertContains(inicio, "cargas sensíveis")
        self.assertContains(inicio, reverse("login"))
