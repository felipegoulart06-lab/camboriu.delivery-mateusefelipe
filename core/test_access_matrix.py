"""Matriz de acesso: cada rota do sistema conferida em todos os tipos de conta.

O teste de cobertura no fim do arquivo falha se alguém publicar uma rota nova
sem dizer aqui quem pode abrir. Assim nenhuma tela fica sem dono.
"""
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import get_resolver, reverse
from django.utils import timezone

from accounts.models import Company, User
from finance.models import DriverPayout, Invoice
from operations.models import ChecklistPhoto, Delivery, Driver, PickupChecklist, Vehicle
from operations.tests import fake_document, fake_photo

MEDIA_FOR_TESTS = tempfile.mkdtemp(prefix="camboriu-acesso-")

# Perfis de acesso, na mesma ordem dos decoradores em operations/permissions.py.
PUBLICO = "publico"
AUTENTICADO = "autenticado"
PAINEL_EMPRESA = "painel_empresa"
CADASTRO_EMPRESA = "cadastro_empresa"
SOLICITACOES = "solicitacoes"
RECURSOS = "recursos"
PLATAFORMA = "plataforma"
MASTER = "master"
AO_VIVO = "ao_vivo"
ENTREGADOR = "entregador"
SO_POST = "so_post"

ATORES = (
    "anonimo", "master", "central", "proprietario", "administrador",
    "operador", "visualizador", "entregador", "empresa_sem_cadastro",
)
EQUIPE = ("master", "central")
EMPRESA = ("proprietario", "administrador", "operador", "visualizador")


def ok():
    return ("ok", None)


def vai_para(nome):
    return ("redirect", nome)


def erro(codigo):
    return ("status", codigo)


def esperado(acesso, ator):
    """O que cada perfil deve receber em uma rota deste tipo de acesso."""
    if acesso == PUBLICO:
        return ok()
    if acesso == SO_POST:
        return erro(405)
    if ator == "anonimo":
        return ("login", None)

    empresa_pendente = ator == "empresa_sem_cadastro"
    if acesso == AUTENTICADO:
        if ator == "entregador":
            return vai_para("driver_home")
        if ator in EQUIPE:
            return vai_para("platform_home")
        return vai_para("company_profile") if empresa_pendente else ok()
    if acesso == PAINEL_EMPRESA:
        if ator == "entregador":
            return vai_para("driver_home")
        return vai_para("company_profile") if empresa_pendente else ok()
    if acesso == CADASTRO_EMPRESA:
        if ator == "entregador":
            return vai_para("driver_home")
        if ator in EQUIPE:
            return vai_para("platform_home")
        if ator in ("operador", "visualizador"):
            return vai_para("dashboard")
        return ok()
    if acesso in (SOLICITACOES, RECURSOS):
        if ator == "entregador":
            return vai_para("driver_home")
        if empresa_pendente:
            return vai_para("company_profile")
        sem_permissao = ("visualizador",) if acesso == SOLICITACOES else ("operador", "visualizador")
        return vai_para("dashboard") if ator in sem_permissao else ok()
    if acesso == PLATAFORMA:
        if ator == "entregador":
            return vai_para("driver_home")
        return ok() if ator in EQUIPE else vai_para("dashboard")
    if acesso == MASTER:
        if ator == "entregador":
            return vai_para("driver_home")
        if ator == "master":
            return ok()
        return vai_para("platform_home") if ator == "central" else vai_para("dashboard")
    if acesso == ENTREGADOR:
        if ator == "entregador":
            return ok()
        return vai_para("platform_home") if ator in EQUIPE else vai_para("dashboard")
    if acesso == AO_VIVO:
        return ok()
    raise AssertionError(f"Perfil de acesso desconhecido: {acesso}")


class Rota:
    """Uma rota do sistema com o perfil de acesso e as exceções conhecidas."""

    def __init__(self, nome, acesso, args=(), post_only=False, excecoes=None):
        self.nome = nome
        self.acesso = acesso
        self.args = args
        self.post_only = post_only
        self.excecoes = excecoes or {}

    def url(self, caso):
        argumentos = [valor(caso) if callable(valor) else valor for valor in self.args]
        return reverse(self.nome, args=argumentos)

    def esperado(self, ator):
        if ator in self.excecoes:
            return self.excecoes[ator]
        resultado = esperado(self.acesso, ator)
        if self.post_only and resultado == ok():
            return erro(405)
        return resultado


# Atalhos para os objetos criados no setUp, resolvidos na hora de montar a URL.
entrega = lambda caso: caso.entrega.pk  # noqa: E731
entrega_aberta = lambda caso: caso.entrega_aberta.pk  # noqa: E731
corrida_coleta = lambda caso: caso.corrida_coleta.pk  # noqa: E731
corrida_transito = lambda caso: caso.corrida_transito.pk  # noqa: E731
foto = lambda caso: caso.foto.pk  # noqa: E731
empresa_a = lambda caso: caso.empresa_a.pk  # noqa: E731
usuario_a = lambda caso: caso.administrador.pk  # noqa: E731
motorista_a = lambda caso: caso.motorista_a.pk  # noqa: E731
motorista_plataforma = lambda caso: caso.motorista_plataforma.pk  # noqa: E731
veiculo_a = lambda caso: caso.veiculo_a.pk  # noqa: E731
fatura = lambda caso: caso.fatura.pk  # noqa: E731
repasse = lambda caso: caso.repasse.pk  # noqa: E731

SEM_EMPRESA = {ator: erro(404) for ator in EQUIPE}

ROTAS = (
    # Público e entrada
    Rota("landing", PUBLICO),
    Rota("login", PUBLICO),
    Rota("logout", SO_POST),
    Rota("switch_account", SO_POST),
    Rota("dashboard", AUTENTICADO),
    Rota("live_alerts", AO_VIVO),

    # Painel da empresa contratante
    Rota("company_profile", CADASTRO_EMPRESA),
    Rota("company_own_dossier", CADASTRO_EMPRESA),
    Rota("company_own_document", CADASTRO_EMPRESA, ["address_proof"],
         excecoes={"empresa_sem_cadastro": erro(404)}),
    Rota("delivery_list", PAINEL_EMPRESA),
    Rota("delivery_create", SOLICITACOES, excecoes={
        "master": vai_para("platform_delivery_create"),
        "central": vai_para("platform_delivery_create"),
    }),
    Rota("delivery_detail", PAINEL_EMPRESA, [entrega]),
    Rota("delivery_edit", SOLICITACOES, [entrega]),
    Rota("delivery_tracking", PAINEL_EMPRESA, [corrida_transito]),
    Rota("delivery_tracking_data", PAINEL_EMPRESA, [corrida_transito]),
    Rota("delivery_checklist", PAINEL_EMPRESA, [corrida_transito]),
    Rota("checklist_photo", PAINEL_EMPRESA, [corrida_transito, foto]),
    Rota("driver_list", PLATAFORMA),
    Rota("driver_create", MASTER),
    Rota("driver_edit", MASTER, [motorista_a]),
    Rota("driver_document", PLATAFORMA, [motorista_a, "cnh_front"]),
    Rota("driver_dossier", PLATAFORMA, [motorista_a]),
    Rota("vehicle_list", PLATAFORMA),
    Rota("vehicle_create", MASTER),
    Rota("vehicle_edit", MASTER, [veiculo_a]),
    Rota("vehicle_document", PLATAFORMA, [veiculo_a, "crlv_document"]),
    Rota("vehicle_dossier", PLATAFORMA, [veiculo_a]),

    # Financeiro visto pela empresa
    Rota("company_billing", PAINEL_EMPRESA, excecoes=SEM_EMPRESA),
    Rota("company_invoice_request", CADASTRO_EMPRESA,
         excecoes={"empresa_sem_cadastro": vai_para("company_billing")}),
    Rota("company_invoice_detail", PAINEL_EMPRESA, [fatura],
         excecoes={**SEM_EMPRESA, "empresa_sem_cadastro": vai_para("company_profile")}),
    Rota("company_invoice_document", PAINEL_EMPRESA, [fatura],
         excecoes={**SEM_EMPRESA, "empresa_sem_cadastro": vai_para("company_profile")}),
    Rota("company_delivery_document", PAINEL_EMPRESA, [corrida_transito]),
    Rota("company_notifications", PAINEL_EMPRESA),
    Rota("company_notifications_read", PAINEL_EMPRESA, post_only=True),

    # Central de despacho
    Rota("platform_home", PLATAFORMA),
    Rota("dispatch_board", PLATAFORMA),
    Rota("platform_deliveries", PLATAFORMA),
    Rota("platform_delivery_create", PLATAFORMA),
    Rota("dispatch_detail", PLATAFORMA, [entrega]),
    Rota("dispatch_delivery", PLATAFORMA, [entrega]),
    Rota("dispatch_confirm", PLATAFORMA, [entrega], post_only=True),
    Rota("dispatch_cancel", PLATAFORMA, [entrega], post_only=True),
    Rota("platform_drivers", PLATAFORMA),
    Rota("platform_driver_create", MASTER),
    Rota("platform_driver_edit", MASTER, [motorista_plataforma]),
    Rota("platform_driver_dossier", PLATAFORMA, [motorista_plataforma]),
    Rota("platform_integration", PLATAFORMA),
    Rota("platform_integration_pdf", PLATAFORMA),

    # Cadastros exclusivos do admin master
    Rota("company_list", MASTER),
    Rota("company_create", MASTER),
    Rota("company_detail", MASTER, [empresa_a]),
    Rota("company_dossier", MASTER, [empresa_a]),
    Rota("company_edit", MASTER, [empresa_a]),
    Rota("company_toggle", MASTER, [empresa_a], post_only=True),
    Rota("company_document", MASTER, [empresa_a, "address_proof"]),
    Rota("company_user_create", MASTER, [empresa_a]),
    Rota("company_user_edit", MASTER, [empresa_a, usuario_a]),
    Rota("user_password", MASTER, [usuario_a]),
    Rota("platform_team", MASTER),
    Rota("platform_team_create", MASTER),
    Rota("platform_team_edit", MASTER, [lambda caso: caso.central.pk]),

    # Contabilidade
    Rota("finance_dashboard", PLATAFORMA),
    Rota("finance_pricing", MASTER),
    Rota("delivery_price", PLATAFORMA, [entrega_aberta]),
    Rota("invoice_list", PLATAFORMA),
    Rota("invoice_detail", PLATAFORMA, [fatura]),
    Rota("invoice_document", PLATAFORMA, [fatura]),
    Rota("invoice_bank_slip", MASTER, [fatura]),
    Rota("invoice_pay", MASTER, [fatura], post_only=True),
    Rota("invoice_cancel", MASTER, [fatura], post_only=True),
    Rota("invoice_create", MASTER, [empresa_a]),
    Rota("payout_list", PLATAFORMA),
    Rota("payout_create", MASTER),
    Rota("payout_detail", PLATAFORMA, [repasse]),
    Rota("payout_pay", MASTER, [repasse], post_only=True),
    Rota("payout_reopen", MASTER, [repasse], post_only=True),
    Rota("notification_list", PLATAFORMA),
    Rota("notifications_read", PLATAFORMA, post_only=True),
    Rota("delivery_document", PLATAFORMA, [entrega]),

    # Painel do entregador
    Rota("driver_home", ENTREGADOR),
    Rota("driver_jobs", ENTREGADOR),
    Rota("driver_history", ENTREGADOR),
    Rota("driver_profile", ENTREGADOR),
    Rota("driver_availability", ENTREGADOR, post_only=True),
    Rota("driver_job_detail", ENTREGADOR, [corrida_coleta]),
    Rota("driver_job_document", ENTREGADOR, [corrida_coleta]),
    Rota("driver_accept_job", ENTREGADOR, [corrida_coleta], post_only=True),
    Rota("driver_start_pickup", ENTREGADOR, [corrida_coleta], post_only=True),
    Rota("driver_checklist", ENTREGADOR, [corrida_coleta]),
    Rota("driver_complete_job", ENTREGADOR, [corrida_transito]),
    Rota("driver_ping", ENTREGADOR, [corrida_transito], post_only=True),
)


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class MatrizDeAcessoTests(TestCase):
    """Abre todas as telas com cada conta e confere quem entra, quem é desviado e quem é barrado."""

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
        self.empresa_a = Company.objects.create(
            name="Empresa Alfa", legal_name="Alfa Comércio LTDA", slug="alfa",
            document="22.333.444/0001-55", document_type=Company.DocumentType.CNPJ,
            city="Balneário Camboriú", state="SC", registered_at=agora,
            address_proof=fake_document("comprovante.pdf"),
        )
        self.empresa_nova = Company.objects.create(name="Nova", slug="nova", document="55.666.777/0001-99")

        def conta(username, papel, empresa):
            return User.objects.create_user(username, password="Acesso@2026", company=empresa, role=papel)

        self.master = conta("master@teste.local", User.Role.MASTER, self.plataforma)
        self.central = conta("central@teste.local", User.Role.DISPATCHER, self.plataforma)
        self.proprietario = conta("dono@alfa.local", User.Role.OWNER, self.empresa_a)
        self.administrador = conta("admin@alfa.local", User.Role.ADMIN, self.empresa_a)
        self.operador = conta("operador@alfa.local", User.Role.OPERATOR, self.empresa_a)
        self.visualizador = conta("visual@alfa.local", User.Role.VIEWER, self.empresa_a)
        self.sem_cadastro = conta("dono@nova.local", User.Role.OWNER, self.empresa_nova)
        self.entregador = conta("carlos@teste.local", User.Role.DRIVER, self.plataforma)

        self.motorista_plataforma = Driver.objects.create(
            company=self.plataforma, user=self.entregador, name="Carlos Mendes", cpf="1", cnh="1",
            cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE,
            status=Driver.Status.ACTIVE,
        )
        self.motorista_a = Driver.objects.create(
            company=self.empresa_a, name="Frota Alfa", cpf="2", cnh="2", cnh_category="B",
            phone="(47) 99911-3300", contract_type=Driver.Contract.EMPLOYEE, cnh_front=fake_photo(),
        )
        self.veiculo_a = Vehicle.objects.create(
            company=self.empresa_a, kind=Vehicle.Kind.CAR, plate="ALF1A23", brand="Fiat",
            model="Fiorino", year=2023, crlv_document=fake_document("crlv.pdf"),
        )
        Vehicle.objects.create(
            company=self.plataforma, kind=Vehicle.Kind.MOTORCYCLE, plate="CDL1B34",
            brand="Honda", model="CG 160", year=2025,
        )

        self.entrega = self._entrega("Recepção")
        self.entrega_aberta = self._entrega("Faturar", status=Delivery.Status.DELIVERED, preco="30.00")
        self.entrega_faturada = self._entrega("Faturada", status=Delivery.Status.DELIVERED, preco="45.00")
        self.corrida_coleta = self._entrega("Coleta", status=Delivery.Status.PICKUP)
        self.corrida_transito = self._entrega("Trânsito", status=Delivery.Status.IN_TRANSIT)
        Delivery.objects.filter(pk__in=[self.corrida_coleta.pk, self.corrida_transito.pk, self.entrega_aberta.pk, self.entrega_faturada.pk]).update(
            master_confirmed_at=agora,
        )
        self.corrida_coleta.refresh_from_db()
        self.corrida_transito.refresh_from_db()

        self.fatura = Invoice.create_for(
            self.empresa_a, [self.entrega_faturada], timezone.localdate() + timedelta(days=10),
        )
        entrega_do_repasse = self._entrega("Repasse", status=Delivery.Status.DELIVERED, preco="30.00")
        self.repasse = DriverPayout.create_for(
            self.motorista_plataforma, [entrega_do_repasse], timezone.localdate(), timezone.localdate(),
        )

        checklist = PickupChecklist.objects.create(
            company=self.empresa_a, delivery=self.corrida_transito, driver=self.motorista_plataforma,
            handover_name="Recepção", handover_document="123.456.789-09", package_count=1,
            identity_checked=True, item_matches_request=True, packaging_intact=True,
            seal_applied=True, documents_checked=True, photos_are_original=True,
            submitted_at=agora,
        )
        self.foto = ChecklistPhoto.objects.create(
            checklist=checklist, slot=ChecklistPhoto.Slot.SITE, image=fake_photo(),
        )

    def _entrega(self, solicitante, status=Delivery.Status.REQUESTED, preco=None):
        entrega = Delivery.objects.create(
            company=self.empresa_a, requester=solicitante, item_type=Delivery.ItemType.DOCUMENT,
            description="Teste de acesso", pickup_address="Av. Brasil, 1000", pickup_contact="Recepção",
            delivery_address="Rua das Flores, 10", delivery_contact="Responsável",
            driver=self.motorista_plataforma, status=status,
        )
        if preco:
            Delivery.objects.filter(pk=entrega.pk).update(
                price=Decimal(preco), driver_payout_amount=Decimal(preco) / 2,
            )
            entrega.refresh_from_db()
        return entrega

    def _entrar(self, ator):
        self.client.logout()
        if ator != "anonimo":
            self.client.force_login(getattr(self, "sem_cadastro" if ator == "empresa_sem_cadastro" else ator))

    def _conferir(self, rota, ator, url, resposta):
        tipo, alvo = rota.esperado(ator)
        if tipo == "ok":
            self.assertEqual(resposta.status_code, 200, f"{rota.nome} deveria abrir para {ator}")
        elif tipo == "status":
            self.assertEqual(resposta.status_code, alvo, f"{rota.nome} para {ator}")
        elif tipo == "login":
            self.assertEqual(resposta.status_code, 302, f"{rota.nome} deveria exigir login")
            self.assertEqual(resposta.headers["Location"], f"{reverse('login')}?next={url}")
        else:
            self.assertEqual(resposta.status_code, 302, f"{rota.nome} deveria desviar {ator}")
            self.assertEqual(resposta.headers["Location"], reverse(alvo), f"{rota.nome} para {ator}")

    def test_toda_rota_responde_o_esperado_em_cada_tipo_de_conta(self):
        for ator in ATORES:
            self._entrar(ator)
            for rota in ROTAS:
                url = rota.url(self)
                with self.subTest(conta=ator, rota=rota.nome):
                    self._conferir(rota, ator, url, self.client.get(url))

    def test_nenhuma_rota_fica_fora_da_matriz(self):
        publicadas = {
            nome for nome in get_resolver().reverse_dict.keys() if isinstance(nome, str)
        }
        cobertas = {rota.nome for rota in ROTAS}
        self.assertEqual(
            publicadas - cobertas, set(),
            "Rota publicada sem definir quem pode abrir. Inclua na matriz de acesso.",
        )
        self.assertEqual(cobertas - publicadas, set(), "A matriz cita rota que não existe mais.")

    def test_area_administrativa_do_django_e_so_do_superusuario(self):
        url = reverse("admin:index")
        self.client.force_login(self.master)
        self.assertEqual(self.client.get(url).status_code, 302)
        raiz = User.objects.create_superuser(
            "root@teste.local", "root@teste.local", "Acesso@2026", company=self.plataforma, role=User.Role.MASTER,
        )
        self.client.force_login(raiz)
        self.assertEqual(self.client.get(url).status_code, 200)
