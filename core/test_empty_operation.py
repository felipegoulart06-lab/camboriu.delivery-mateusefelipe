"""Operação recém-instalada e área administrativa do Django.

Tela vazia é onde template quebra: contador sem registro, lista sem linha, gráfico
sem série. Aqui todas as páginas sem parâmetro são abertas com o banco zerado.
"""
from io import StringIO

from django.contrib import admin
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from accounts.models import Company, User
from core.defaults import MASTER_EMAIL
from operations.models import Driver

PAGINAS_DO_MASTER = (
    "platform_home", "dispatch_board", "platform_deliveries", "company_list", "company_create",
    "platform_team", "platform_team_create", "platform_drivers", "platform_driver_create",
    "platform_integration", "finance_dashboard", "finance_pricing", "invoice_list",
    "payout_list", "payout_create", "notification_list",
    "delivery_list", "delivery_create", "driver_list", "driver_create",
    "vehicle_list", "vehicle_create",
)

PAGINAS_DA_EMPRESA = (
    "dashboard", "delivery_list", "delivery_create", "driver_list", "vehicle_list",
    "company_profile", "company_billing",
)

PAGINAS_DO_ENTREGADOR = ("driver_home", "driver_jobs", "driver_history", "driver_profile")


class OperacaoVaziaTests(TestCase):
    """Nenhuma tela pode quebrar antes do primeiro cadastro."""

    def setUp(self):
        call_command("reset_operation", yes=True, stdout=StringIO())
        self.plataforma = Company.objects.platform()
        self.master = User.objects.get(username=MASTER_EMAIL)

    def abrir_todas(self, paginas):
        for nome in paginas:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 200, f"{nome} quebrou sem dados")

    def test_master_abre_todo_o_painel_com_o_banco_zerado(self):
        self.client.force_login(self.master)
        self.abrir_todas(PAGINAS_DO_MASTER)

    def test_empresa_recem_cadastrada_abre_o_painel_sem_nenhuma_entrega(self):
        empresa = Company.objects.create(
            name="Nova Empresa", slug="nova", document="44.555.666/0001-81",
            registered_at=self.plataforma.registered_at,
        )
        dono = User.objects.create_user("dono@nova.local", password="Acesso@2026", company=empresa, role=User.Role.OWNER)
        self.client.force_login(dono)
        self.abrir_todas(PAGINAS_DA_EMPRESA)

    def test_entregador_sem_corrida_abre_o_painel_do_celular(self):
        login = User.objects.create_user("novo@entrega.local", password="Acesso@2026", company=self.plataforma, role=User.Role.DRIVER)
        Driver.objects.create(
            company=self.plataforma, user=login, name="Novato", cpf="9", cnh="9", cnh_category="A",
            phone="(47) 99900-0000", contract_type=Driver.Contract.PARTNER,
        )
        self.client.force_login(login)
        self.abrir_todas(PAGINAS_DO_ENTREGADOR)

    def test_primeiro_entregador_so_e_cadastrado_com_a_transportadora_no_ar(self):
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse("platform_driver_create")).status_code, 200)
        self.assertIsNotNone(Company.objects.platform())


class AdministracaoDjangoTests(TestCase):
    """O /admin/ é a última linha de suporte: todo modelo registrado precisa abrir."""

    def setUp(self):
        call_command("reset_operation", yes=True, stdout=StringIO())
        self.raiz = User.objects.create_superuser(
            "root@teste.local", "root@teste.local", "Acesso@2026",
            company=Company.objects.platform(), role=User.Role.MASTER,
        )
        self.client.force_login(self.raiz)

    def test_todos_os_modelos_registrados_listam_e_abrem_o_formulario(self):
        self.assertEqual(self.client.get(reverse("admin:index")).status_code, 200)
        for modelo, opcoes in admin.site._registry.items():
            rotulo = f"{modelo._meta.app_label}_{modelo._meta.model_name}"
            with self.subTest(modelo=rotulo):
                lista = self.client.get(reverse(f"admin:{rotulo}_changelist"))
                self.assertEqual(lista.status_code, 200)
                if opcoes.has_add_permission(lista.wsgi_request):
                    self.assertEqual(self.client.get(reverse(f"admin:{rotulo}_add")).status_code, 200)

    def test_historico_da_operacao_nao_pode_ser_apagado_pelo_admin(self):
        from operations.models import Delivery, DeliveryEvent, PickupChecklist

        for modelo in (Delivery, DeliveryEvent, PickupChecklist):
            rotulo = f"{modelo._meta.app_label}_{modelo._meta.model_name}"
            with self.subTest(modelo=rotulo):
                opcoes = admin.site._registry[modelo]
                pedido = self.client.get(reverse(f"admin:{rotulo}_changelist")).wsgi_request
                self.assertFalse(opcoes.has_delete_permission(pedido))
                self.assertNotIn("delete_selected", opcoes.get_actions(pedido))
