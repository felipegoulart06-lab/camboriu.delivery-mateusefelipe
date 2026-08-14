"""Configurações, validações de documento e regras dos anexos.

É a camada que não aparece na tela, mas derruba a operação quando sai errada:
CPF que passa sem ser CPF, arquivo grande demais, banco mal configurado no deploy.
"""
import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from accounts.models import Company
from config.settings import database_from_url, load_env_file, postgres_config
from core.uploads import company_document_path, document_path, serve, validate_document_file
from core.validators import (
    clean_chassis, clean_cnpj, clean_cpf, clean_phone, clean_plate, clean_renavam, clean_zip_code,
)


class ValidacaoDeDocumentosTests(SimpleTestCase):
    """Documento inválido não pode entrar no cadastro nem sair no contrato."""

    def test_cpf_valido_sai_formatado(self):
        self.assertEqual(clean_cpf("32165498791"), "321.654.987-91")
        self.assertEqual(clean_cpf("987.654.321-00"), "987.654.321-00")

    def test_cpf_invalido_e_recusado(self):
        for valor in ("111.111.111-11", "123.456.789-00", "1234", ""):
            with self.subTest(cpf=valor), self.assertRaises(ValidationError):
                clean_cpf(valor)

    def test_cnpj_valido_sai_formatado(self):
        self.assertEqual(clean_cnpj("44555666000181"), "44.555.666/0001-81")
        self.assertEqual(clean_cnpj("12.345.678/0001-95"), "12.345.678/0001-95")

    def test_cnpj_invalido_e_recusado(self):
        for valor in ("11.111.111/1111-11", "12345678000100", "123", ""):
            with self.subTest(cnpj=valor), self.assertRaises(ValidationError):
                clean_cnpj(valor)

    def test_placa_aceita_padrao_antigo_e_mercosul(self):
        self.assertEqual(clean_plate("abc-1234"), "ABC1234")
        self.assertEqual(clean_plate("abc1d23"), "ABC1D23")
        for valor in ("12345", "ABCD123", "AB1C234"):
            with self.subTest(placa=valor), self.assertRaises(ValidationError):
                clean_plate(valor)

    def test_renavam_confere_o_digito_verificador(self):
        self.assertEqual(clean_renavam("11122233307"), "11122233307")
        for valor in ("11122233300", "123"):
            with self.subTest(renavam=valor), self.assertRaises(ValidationError):
                clean_renavam(valor)

    def test_chassi_tem_17_posicoes_e_nao_usa_i_o_q(self):
        self.assertEqual(clean_chassis("9bd25519mc1000456"), "9BD25519MC1000456")
        for valor in ("9BD25519MC100045", "9BD2551OMC1000456", "ABC"):
            with self.subTest(chassi=valor), self.assertRaises(ValidationError):
                clean_chassis(valor)

    def test_cep_e_telefone_saem_no_formato_de_impressao(self):
        self.assertEqual(clean_zip_code("88330100"), "88330-100")
        self.assertEqual(clean_phone("4733001234"), "(47) 3300-1234")
        self.assertEqual(clean_phone("47999001122"), "(47) 99900-1122")
        for valor in ("1234", "479990011223"):
            with self.subTest(telefone=valor), self.assertRaises(ValidationError):
                clean_phone(valor)


class AnexosTests(TestCase):
    """Os anexos são prova documental: formato conferido, tamanho limitado e pasta por empresa."""

    def test_so_aceita_foto_ou_pdf(self):
        self.assertIsNotNone(validate_document_file(SimpleUploadedFile("cnh.jpg", b"conteudo")))
        self.assertIsNotNone(validate_document_file(SimpleUploadedFile("contrato.pdf", b"%PDF")))
        for nome in ("script.exe", "planilha.xlsx", "arquivo"):
            with self.subTest(arquivo=nome), self.assertRaises(ValidationError):
                validate_document_file(SimpleUploadedFile(nome, b"conteudo"))

    @override_settings(CHECKLIST_MAX_PHOTO_MB=1)
    def test_arquivo_acima_do_limite_e_recusado(self):
        grande = SimpleUploadedFile("foto.jpg", b"x" * (1024 * 1024 + 1))
        with self.assertRaises(ValidationError):
            validate_document_file(grande)

    def test_cada_anexo_vai_para_a_pasta_da_empresa(self):
        empresa = Company.objects.create(name="Alfa", slug="alfa", document="22.333.444/0001-55")
        caminho = document_path("motoristas")(type("Falso", (), {"company_id": empresa.pk, "pk": 1})(), "cnh.JPG")
        self.assertTrue(caminho.startswith(f"documentos/motoristas/{empresa.pk}/"))
        self.assertTrue(caminho.endswith(".jpg"))
        self.assertTrue(company_document_path(empresa, "contrato.pdf").startswith("documentos/empresas/alfa/"))

    def test_upload_to_e_comparavel_para_as_migracoes(self):
        self.assertEqual(document_path("motoristas"), document_path("motoristas"))
        self.assertNotEqual(document_path("motoristas"), document_path("veiculos"))

    def test_campo_desconhecido_ou_vazio_nao_baixa_arquivo(self):
        empresa = Company.objects.create(name="Beta", slug="beta", document="44.555.666/0001-81")
        with self.assertRaises(Http404):
            serve(empresa, "senha", Company.DOCUMENTS)
        with self.assertRaises(Http404):
            serve(empresa, "address_proof", Company.DOCUMENTS)


class ConfiguracaoDoBancoTests(SimpleTestCase):
    """A string de conexão do Supabase precisa virar configuração segura."""

    def test_url_do_supabase_vira_conexao_com_tls(self):
        config = database_from_url(
            "postgresql://postgres.abc:Senha%40Forte@aws-0-sa-east-1.pooler.supabase.com:5432/postgres"
        )
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(config["USER"], "postgres.abc")
        self.assertEqual(config["PASSWORD"], "Senha@Forte")
        self.assertEqual(config["HOST"], "aws-0-sa-east-1.pooler.supabase.com")
        self.assertEqual(config["PORT"], "5432")
        self.assertEqual(config["NAME"], "postgres")
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")

    def test_url_sem_postgres_e_recusada(self):
        with self.assertRaises(ImproperlyConfigured):
            database_from_url("mysql://usuario:senha@localhost:3306/banco")

    def test_pooler_em_modo_transacao_nao_guarda_conexao(self):
        transacao = postgres_config("postgres", "u", "s", "aws-0-sa-east-1.pooler.supabase.com", "6543")
        self.assertEqual(transacao["CONN_MAX_AGE"], 0)
        self.assertTrue(transacao["DISABLE_SERVER_SIDE_CURSORS"])
        self.assertFalse(transacao["CONN_HEALTH_CHECKS"])

        sessao = postgres_config("postgres", "u", "s", "db.abc.supabase.co", "5432")
        self.assertGreater(sessao["CONN_MAX_AGE"], 0)
        self.assertFalse(sessao["DISABLE_SERVER_SIDE_CURSORS"])

    def test_env_do_projeto_nao_sobrescreve_a_variavel_do_servidor(self):
        pasta = Path(tempfile.mkdtemp(prefix="camboriu-env-"))
        (pasta / ".env").write_text(
            "# comentário\nCAMBORIU_TESTE_NOVA=do-arquivo\nCAMBORIU_TESTE_EXISTENTE=\"do-arquivo\"\nlinha-solta\n",
            encoding="utf-8",
        )
        os.environ["CAMBORIU_TESTE_EXISTENTE"] = "do-servidor"
        self.addCleanup(os.environ.pop, "CAMBORIU_TESTE_EXISTENTE", None)
        self.addCleanup(os.environ.pop, "CAMBORIU_TESTE_NOVA", None)

        load_env_file(pasta / ".env")
        self.assertEqual(os.environ["CAMBORIU_TESTE_NOVA"], "do-arquivo")
        self.assertEqual(os.environ["CAMBORIU_TESTE_EXISTENTE"], "do-servidor")

    def test_arquivo_inexistente_nao_quebra_a_inicializacao(self):
        self.assertIsNone(load_env_file(Path(tempfile.gettempdir()) / "nao-existe-camboriu.env"))


class ConfiguracaoDaAplicacaoTests(SimpleTestCase):
    """Ajustes que o deploy depende: estáticos, sessão, limites de upload e mapa."""

    def test_estaticos_saem_pelo_whitenoise(self):
        self.assertIn("whitenoise.middleware.WhiteNoiseMiddleware", settings.MIDDLEWARE)
        self.assertLess(
            settings.MIDDLEWARE.index("whitenoise.middleware.WhiteNoiseMiddleware"),
            settings.MIDDLEWARE.index("django.contrib.sessions.middleware.SessionMiddleware"),
        )
        self.assertTrue(settings.STORAGES["staticfiles"]["BACKEND"].startswith("whitenoise.storage."))

    def test_sessao_e_csrf_ficam_fechados_para_script(self):
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)
        self.assertTrue(settings.CSRF_COOKIE_HTTPONLY)
        self.assertEqual(settings.SESSION_COOKIE_SAMESITE, "Lax")
        self.assertEqual(settings.SESSION_ENGINE, "django.contrib.sessions.backends.cached_db")
        self.assertEqual(settings.CSRF_FAILURE_VIEW, "core.auth_views.csrf_failure")

    def test_limites_comportam_o_checklist_de_doze_fotos(self):
        self.assertGreaterEqual(settings.DATA_UPLOAD_MAX_NUMBER_FILES, 12)
        self.assertGreaterEqual(settings.DATA_UPLOAD_MAX_NUMBER_FIELDS, 100)
        self.assertGreaterEqual(settings.CHECKLIST_MAX_PHOTO_MB, 1)

    def test_rastreio_e_mapa_tem_valores_de_operacao(self):
        self.assertGreater(settings.TRACKING_PING_SECONDS, 0)
        self.assertGreater(settings.TRACKING_STALE_SECONDS, settings.TRACKING_PING_SECONDS)
        self.assertIn("{z}", settings.MAP_TILE_URL)
        self.assertAlmostEqual(settings.MAP_DEFAULT_LAT, -26.99, places=1)

    def test_senha_curta_nao_passa_pelos_validadores(self):
        from django.contrib.auth.password_validation import validate_password

        with self.assertRaises(ValidationError):
            validate_password("Curta@12")
        validate_password("Camboriu@2026")


class TokenExpiradoTests(TestCase):
    """Token de CSRF vencido volta ao login com aviso, em vez do 403 técnico."""

    def test_falha_de_csrf_manda_para_o_login(self):
        from core.auth_views import csrf_failure

        pedido = self.client.request().wsgi_request
        resposta = csrf_failure(pedido, reason="token ausente")
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(resposta.url, f"{reverse('login')}?expired=1")

    def test_login_avisa_que_o_token_venceu(self):
        self.assertContains(self.client.get(f"{reverse('login')}?expired=1"), "expirou")
