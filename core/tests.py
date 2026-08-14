from io import StringIO

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from finance.models import PricingPolicy
from operations.models import Delivery, Driver, Vehicle


class AccessTests(TestCase):
    def test_landing_is_public_and_dashboard_requires_login(self):
        self.assertEqual(self.client.get(reverse("landing")).status_code, 200)
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('dashboard')}")

    def test_user_can_login_and_open_dashboard(self):
        company = Company.objects.create(name="Teste", slug="teste", document="99", registered_at=timezone.now())
        User.objects.create_user("user@test.local", password="StrongPass123!", company=company)
        response = self.client.post(reverse("login"), {"username": "user@test.local", "password": "StrongPass123!"})
        self.assertRedirects(response, reverse("dashboard"))
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 200)

    def test_dashboard_sends_a_new_company_to_finish_its_registration(self):
        company = Company.objects.create(name="Nova", slug="nova", document="98")
        User.objects.create_user("nova@test.local", password="StrongPass123!", company=company, role=User.Role.OWNER)
        self.client.login(username="nova@test.local", password="StrongPass123!")
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("company_profile"))


class LoginSecurityTests(TestCase):
    """Força bruta barrada e nenhuma credencial exposta quando o modo demo está desligado."""

    def setUp(self):
        cache.clear()
        self.addCleanup(cache.clear)
        company = Company.objects.create(name="Segura", slug="segura", document="97", registered_at=timezone.now())
        self.user = User.objects.create_user("seguro@test.local", password="StrongPass123!", company=company)

    def _tentativa_errada(self):
        return self.client.post(reverse("login"), {"username": "seguro@test.local", "password": "errada"})

    @override_settings(LOGIN_ATTEMPT_LIMIT=3)
    def test_login_locks_after_too_many_failures(self):
        for _ in range(3):
            self.assertEqual(self._tentativa_errada().status_code, 200)

        bloqueado = self.client.post(
            reverse("login"), {"username": "seguro@test.local", "password": "StrongPass123!"}
        )
        self.assertEqual(bloqueado.status_code, 429)
        self.assertContains(bloqueado, "Muitas tentativas", status_code=429)
        self.assertFalse(bloqueado.wsgi_request.user.is_authenticated)

    @override_settings(LOGIN_ATTEMPT_LIMIT=3)
    def test_successful_login_clears_the_counter(self):
        self._tentativa_errada()
        self._tentativa_errada()
        self.assertRedirects(
            self.client.post(reverse("login"), {"username": "seguro@test.local", "password": "StrongPass123!"}),
            reverse("dashboard"),
        )
        self.client.logout()
        self._tentativa_errada()
        # O contador zerou no acerto, então esta falha isolada não pode bloquear.
        self.assertRedirects(
            self.client.post(reverse("login"), {"username": "seguro@test.local", "password": "StrongPass123!"}),
            reverse("dashboard"),
        )

    @override_settings(DEMO_MODE=False)
    def test_login_page_hides_demo_accounts_in_production(self):
        pagina = self.client.get(reverse("login")).content.decode()
        self.assertNotIn("master@camboriudelivery.local", pagina)
        self.assertNotIn("Camboriu@123", pagina)

    @override_settings(DEMO_MODE=True)
    def test_login_page_shows_demo_accounts_only_in_demo_mode(self):
        self.assertContains(self.client.get(reverse("login")), "master@camboriudelivery.local")

    def test_security_headers_are_present(self):
        resposta = self.client.get(reverse("login"))
        self.assertEqual(resposta.headers["X-Frame-Options"], "DENY")
        self.assertEqual(resposta.headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(resposta.headers["Referrer-Policy"], "same-origin")


class LoginRedirectTests(TestCase):
    """O ?next= não pode jogar empresa no painel do entregador nem o contrário."""

    def setUp(self):
        self.plataforma = Company.objects.create(
            name="Camboriú Delivery", slug="plataforma", document="11.222.333/0001-81",
            is_platform=True, registered_at=timezone.now(),
        )
        self.empresa = Company.objects.create(
            name="Alfa", slug="alfa", document="44.555.666/0001-81", registered_at=timezone.now(),
        )
        self.dono = User.objects.create_user("dono@alfa.local", password="Acesso@2026", company=self.empresa, role=User.Role.OWNER)
        self.master = User.objects.create_user("master@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.MASTER)
        login_entregador = User.objects.create_user("carlos@teste.local", password="Acesso@2026", company=self.plataforma, role=User.Role.DRIVER)
        Driver.objects.create(
            company=self.plataforma, user=login_entregador, name="Carlos", cpf="1", cnh="1",
            cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE,
        )

    def entrar(self, usuario, destino=""):
        url = f"{reverse('login')}?next={destino}" if destino else reverse("login")
        return self.client.post(url, {"username": usuario, "password": "Acesso@2026"})

    def test_empresa_nao_cai_no_painel_do_entregador(self):
        self.assertRedirects(self.entrar("dono@alfa.local", reverse("driver_home")), reverse("dashboard"))

    def test_empresa_nao_cai_na_central_de_despacho(self):
        self.assertRedirects(self.entrar("dono@alfa.local", reverse("dispatch_board")), reverse("dashboard"))

    def test_empresa_volta_para_a_pagina_pedida_quando_ela_e_do_painel_dela(self):
        self.assertRedirects(self.entrar("dono@alfa.local", reverse("delivery_list")), reverse("delivery_list"))

    def test_equipe_e_entregador_vao_sempre_para_o_proprio_painel(self):
        self.assertRedirects(
            self.entrar("master@teste.local", reverse("delivery_list")), reverse("platform_home"),
        )
        self.client.logout()
        self.assertRedirects(
            self.entrar("carlos@teste.local", reverse("company_billing")), reverse("driver_home"),
            fetch_redirect_response=False,
        )

    def test_sair_do_sistema_devolve_a_tela_de_login(self):
        self.client.force_login(self.dono)
        self.assertRedirects(self.client.post(reverse("logout")), reverse("login"), fetch_redirect_response=False)
        self.assertNotIn("_auth_user_id", self.client.session)


class BootstrapCommandTests(TestCase):
    """A carga inicial da operação real: sem dado inventado e podendo rodar de novo."""

    def _bootstrap(self, **extras):
        saida = StringIO()
        argumentos = {
            "nome": "Camboriú Delivery",
            "cnpj": "11.222.333/0001-81",
            "master_email": "diretoria@camboriudelivery.com.br",
            "senha": "OperacaoReal#2026",
            "cidade": "Balneário Camboriú",
            "uf": "sc",
            "telefone": "4733330000",
            "cep": "88330000",
        }
        argumentos.update(extras)
        call_command("bootstrap", stdout=saida, **argumentos)
        return saida.getvalue()

    def test_creates_platform_company_master_and_pricing(self):
        self._bootstrap()
        empresa = Company.objects.platform()
        self.assertEqual(empresa.name, "Camboriú Delivery")
        self.assertEqual(empresa.document, "11.222.333/0001-81")
        self.assertEqual(empresa.state, "SC")
        self.assertEqual(empresa.phone, "(47) 3333-0000")
        self.assertEqual(empresa.zip_code, "88330-000")
        self.assertTrue(empresa.is_registered)

        master = User.objects.get(username="diretoria@camboriudelivery.com.br")
        self.assertEqual(master.role, User.Role.MASTER)
        self.assertTrue(master.check_password("OperacaoReal#2026"))
        self.assertFalse(master.is_staff)
        self.assertEqual(PricingPolicy.objects.count(), 1)

    def test_running_twice_updates_instead_of_duplicating(self):
        self._bootstrap()
        self._bootstrap(nome="Camboriú Delivery Express", cidade="Camboriú")
        self.assertEqual(Company.objects.filter(is_platform=True).count(), 1)
        self.assertEqual(User.objects.filter(role=User.Role.MASTER).count(), 1)
        self.assertEqual(Company.objects.platform().city, "Camboriú")

    def test_refuses_invalid_document_and_weak_password(self):
        with self.assertRaises(CommandError):
            self._bootstrap(cnpj="11.222.333/0001-00")
        with self.assertRaises(CommandError):
            self._bootstrap(senha="123456")

    def test_requires_master_email(self):
        with self.assertRaises(CommandError):
            self._bootstrap(master_email="")


class ResetOperationCommandTests(TestCase):
    """Depois do reset só existe o admin master. Entregador, empresa cliente e senha velha somem."""

    def test_wipe_leaves_only_the_default_master(self):
        with override_settings(DEMO_MODE=True):
            call_command("seed_demo", stdout=StringIO())
        self.assertTrue(Driver.objects.exists())
        self.assertGreater(User.objects.count(), 1)

        saida = StringIO()
        call_command("reset_operation", yes=True, stdout=saida)

        self.assertEqual(User.objects.count(), 1)
        master = User.objects.get()
        self.assertEqual(master.username, "master@camboriudelivery.local")
        self.assertEqual(master.role, User.Role.MASTER)
        self.assertTrue(master.check_password("Camboriu@123"))
        self.assertEqual(Company.objects.count(), 1)
        self.assertTrue(Company.objects.get().is_platform)
        self.assertFalse(Driver.objects.exists())
        self.assertFalse(Vehicle.objects.exists())
        self.assertFalse(Delivery.objects.exists())
        self.assertIn("Login padrão", saida.getvalue())

    def test_refuses_without_confirmation(self):
        with self.assertRaises(CommandError):
            call_command("reset_operation", stdout=StringIO())


@override_settings(DEMO_MODE=True)
class PurgeDemoCommandTests(TestCase):
    """Depois da limpeza não pode sobrar nenhuma empresa, corrida ou login de demonstração."""

    def setUp(self):
        call_command("seed_demo", stdout=StringIO())

    def test_dry_run_keeps_everything(self):
        saida = StringIO()
        call_command("purge_demo", dry_run=True, stdout=saida)
        self.assertIn("Simulação", saida.getvalue())
        self.assertTrue(Company.objects.filter(slug="demo-camboriu").exists())

    def test_purge_removes_every_demo_record(self):
        self.assertTrue(Delivery.objects.exists())
        call_command("purge_demo", yes=True, stdout=StringIO())

        self.assertFalse(Company.objects.filter(slug__in=("demo-camboriu", "atelie-brisa")).exists())
        self.assertFalse(User.objects.filter(username__endswith="@demo.local").exists())
        self.assertFalse(User.objects.filter(username="carlos@camboriudelivery.local").exists())
        self.assertFalse(Delivery.objects.exists())
        self.assertFalse(Driver.objects.exists())
        self.assertFalse(Vehicle.objects.filter(plate__in=("ABC1D23", "DEF4G56")).exists())

    def test_purge_without_confirmation_is_refused(self):
        with self.assertRaises(CommandError):
            call_command("purge_demo", stdout=StringIO())

    @override_settings(DEMO_MODE=False)
    def test_seed_demo_is_blocked_outside_demo_mode(self):
        with self.assertRaises(CommandError):
            call_command("seed_demo", stdout=StringIO())


class VerifyDatabaseCommandTests(TestCase):
    """O ensaio de ponta a ponta precisa passar e não pode deixar registro para trás."""

    def test_full_cycle_runs_and_rolls_back(self):
        saida = StringIO()
        call_command("verify_database", stdout=saida)
        texto = saida.getvalue()
        self.assertIn("banco intacto", texto)
        self.assertIn("checklist antifraude", texto)
        self.assertIn("repasse", texto)
        self.assertEqual(Company.objects.count(), 0)
        self.assertEqual(Delivery.objects.count(), 0)
        self.assertEqual(User.objects.count(), 0)


class DatabaseHardeningTests(TestCase):
    """A blindagem é só para PostgreSQL/Supabase; nos testes em SQLite ela sai de fininho."""

    def test_harden_is_a_no_op_outside_postgres(self):
        from django.db import connection

        from core.db_security import audit, harden

        if connection.vendor == "postgresql":
            relatorio = harden(connection)
            self.assertEqual(relatorio["sem_rls"], 0)
            self.assertEqual(relatorio["permissoes_publicas"], 0)
        else:
            self.assertIsNone(harden(connection))
            self.assertIsNone(audit(connection))
            call_command("harden_database", stdout=StringIO())

    def test_hardening_runs_after_every_migrate(self):
        from django.apps import apps
        from django.db.models.signals import post_migrate

        chaves = [chave[0] for chave, *_ in post_migrate.receivers if isinstance(chave, tuple)]
        self.assertIn("core.harden_database", chaves)
        # Reenviar o sinal não pode quebrar nada (é o que o `migrate` faz no fim).
        core_config = apps.get_app_config("core")
        post_migrate.send(sender=core_config, app_config=core_config, verbosity=0, interactive=False, using="default")


class VercelDeployTests(TestCase):
    """A Vercel injeta hosts e exige pooler em modo transação. Sem isso o login 400 e o banco cai."""

    def test_preview_and_production_hosts_are_accepted(self):
        from core.deploy import extra_hosts, extra_origins, merge_unique

        env = {
            "VERCEL": "1",
            "VERCEL_URL": "camboriu-delivery-abc.vercel.app",
            "VERCEL_PROJECT_PRODUCTION_URL": "camboriu-delivery.vercel.app",
        }
        hosts = extra_hosts(env)
        self.assertIn("camboriu-delivery-abc.vercel.app", hosts)
        self.assertIn("camboriu-delivery.vercel.app", hosts)
        self.assertIn(".vercel.app", hosts)
        origens = extra_origins(env)
        self.assertIn("https://camboriu-delivery.vercel.app", origens)
        self.assertIn("https://*.vercel.app", origens)
        self.assertIn(".vercel.app", merge_unique(["localhost"], hosts))

    def test_serverless_switches_supabase_pooler_to_transaction_mode(self):
        from core.deploy import serverless_database

        config = serverless_database(
            {
                "ENGINE": "django.db.backends.postgresql",
                "HOST": "aws-0-sa-east-1.pooler.supabase.com",
                "PORT": "5432",
                "CONN_MAX_AGE": 600,
                "OPTIONS": {"sslmode": "require"},
            },
            {"VERCEL": "1"},
        )
        self.assertEqual(config["PORT"], "6543")
        self.assertEqual(config["CONN_MAX_AGE"], 0)
        self.assertTrue(config["DISABLE_SERVER_SIDE_CURSORS"])

    def test_local_postgres_is_left_alone(self):
        from core.deploy import serverless_database

        original = {"ENGINE": "django.db.backends.postgresql", "HOST": "localhost", "PORT": "5432", "CONN_MAX_AGE": 600}
        self.assertEqual(serverless_database(original, {}), original)

    def test_collectstatic_nao_precisa_do_postgres(self):
        from core.deploy import comando_dispensa_banco

        self.assertTrue(comando_dispensa_banco(["manage.py", "collectstatic", "--noinput"]))
        self.assertFalse(comando_dispensa_banco(["manage.py", "runserver"]))
        self.assertFalse(comando_dispensa_banco(["manage.py"]))

    def test_build_da_vercel_consegue_coletar_estaticos_sem_banco(self):
        import os
        import subprocess
        import sys
        from pathlib import Path

        env = os.environ.copy()
        env.update({
            "VERCEL": "1",
            "DEBUG": "0",
            "DEMO_MODE": "0",
            "SECRET_KEY": "vercel-build-test-secret-key-not-for-production",
            "DATABASE_URL": "",
            "DJANGO_SETTINGS_MODULE": "config.settings",
        })
        resultado = subprocess.run(
            [sys.executable, "manage.py", "collectstatic", "--noinput", "-v", "0"],
            cwd=str(Path(__file__).resolve().parent.parent),
            env=env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(resultado.returncode, 0, resultado.stderr + resultado.stdout)
