"""Primeira carga da operação real: a transportadora, o admin master e a tabela de preços.

Diferente do `seed_demo`, aqui nada é inventado — todo dado vem da linha de comando ou do
ambiente, e o comando pode ser repetido para corrigir uma informação sem duplicar nada.
"""

import os
import secrets
import string

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone
from django.utils.text import slugify

from accounts.models import Company, User
from core.validators import clean_cnpj, clean_cpf, clean_phone, clean_zip_code
from finance.models import PricingPolicy

ALFABETO_SENHA = string.ascii_letters + string.digits + "!@#$%&*?"

CAMPOS_TEXTO = {
    "legal_name": "--razao-social",
    "state_registration": "--inscricao-estadual",
    "municipal_registration": "--inscricao-municipal",
    "business_area": "--ramo",
    "email": "--email",
    "address": "--endereco",
    "complement": "--complemento",
    "district": "--bairro",
    "city": "--cidade",
    "contact_name": "--responsavel",
    "contact_role": "--cargo-responsavel",
    "billing_email": "--email-financeiro",
}


class Command(BaseCommand):
    help = "Cria a transportadora da plataforma, o admin master e a tabela de preços inicial."

    def add_arguments(self, parser):
        parser.add_argument("--nome", default=os.getenv("PLATFORM_NAME", ""), help="Nome fantasia da transportadora.")
        parser.add_argument("--razao-social", default=os.getenv("PLATFORM_LEGAL_NAME", ""))
        parser.add_argument("--cnpj", default=os.getenv("PLATFORM_CNPJ", ""))
        parser.add_argument("--inscricao-estadual", default="")
        parser.add_argument("--inscricao-municipal", default="")
        parser.add_argument("--ramo", default="Transporte rodoviário de cargas")
        parser.add_argument("--email", default=os.getenv("PLATFORM_EMAIL", ""))
        parser.add_argument("--telefone", default=os.getenv("PLATFORM_PHONE", ""))
        parser.add_argument("--cep", default=os.getenv("PLATFORM_ZIP", ""))
        parser.add_argument("--endereco", default=os.getenv("PLATFORM_ADDRESS", ""))
        parser.add_argument("--complemento", default="")
        parser.add_argument("--bairro", default="")
        parser.add_argument("--cidade", default=os.getenv("PLATFORM_CITY", ""))
        parser.add_argument("--uf", default=os.getenv("PLATFORM_STATE", ""))
        parser.add_argument("--responsavel", default=os.getenv("PLATFORM_CONTACT", ""))
        parser.add_argument("--cpf-responsavel", default="")
        parser.add_argument("--cargo-responsavel", default="")
        parser.add_argument("--email-financeiro", default="")
        parser.add_argument("--master-email", default=os.getenv("MASTER_EMAIL", ""), help="Login do admin master.")
        parser.add_argument("--master-nome", default=os.getenv("MASTER_NAME", ""))
        parser.add_argument("--senha", default=os.getenv("MASTER_PASSWORD", ""), help="Se vazio, sorteia uma senha forte.")

    def handle(self, *args, **options):
        platform = Company.objects.platform()
        if platform is None and not (options["nome"] and options["cnpj"]):
            raise CommandError("Na primeira execução informe --nome e --cnpj da transportadora.")
        if not options["master_email"]:
            raise CommandError("Informe --master-email (login do admin master).")

        dados = self._dados_da_empresa(options, criando=platform is None)
        senha, sorteada = self._senha(options["senha"])

        with transaction.atomic():
            if platform is None:
                platform = Company.objects.create(
                    slug=self._slug(options["nome"]), is_platform=True, registered_at=timezone.now(), **dados
                )
                acao = "criada"
            else:
                for campo, valor in dados.items():
                    setattr(platform, campo, valor)
                platform.is_platform = True
                platform.registered_at = platform.registered_at or timezone.now()
                platform.is_active = True
                platform.save()
                acao = "atualizada"

            master, novo = User.objects.get_or_create(
                username=options["master_email"], defaults={"email": options["master_email"]}
            )
            nome = (options["master_nome"] or "Admin Master").split(" ", 1)
            master.email = options["master_email"]
            master.company = platform
            master.role = User.Role.MASTER
            master.first_name = nome[0]
            master.last_name = nome[1] if len(nome) > 1 else ""
            master.is_active = True
            if novo or options["senha"] or sorteada:
                master.set_password(senha)
            master.save()

            politica = PricingPolicy.current()

        self.stdout.write(self.style.SUCCESS(f"Transportadora {acao}: {platform.name} · {platform.document}"))
        self.stdout.write(self.style.SUCCESS(f"Admin master {'criado' if novo else 'atualizado'}: {master.username}"))
        if novo or options["senha"] or sorteada:
            self.stdout.write(self.style.WARNING(f"Senha do admin master: {senha}"))
            self.stdout.write("Guarde agora — ela não volta a ser exibida. Troque no primeiro acesso.")
        self.stdout.write(f"Tabela de preços: base R$ {politica.base_price} e {politica.driver_share_percent}% para o entregador.")
        self.stdout.write("Próximo passo: cadastre as empresas clientes e os entregadores pelo painel do admin master.")

    def _dados_da_empresa(self, options, criando):
        dados = {}
        if options["nome"]:
            dados["name"] = options["nome"]
        if options["cnpj"]:
            dados["document"] = self._documento(options["cnpj"])
            dados["document_type"] = (
                Company.DocumentType.CNPJ if len(dados["document"]) == 18 else Company.DocumentType.CPF
            )
        if options["telefone"]:
            dados["phone"] = self._valida(clean_phone, options["telefone"], "--telefone")
        if options["cep"]:
            dados["zip_code"] = self._valida(clean_zip_code, options["cep"], "--cep")
        if options["cpf_responsavel"]:
            dados["contact_document"] = self._valida(clean_cpf, options["cpf_responsavel"], "--cpf-responsavel")
        if options["uf"]:
            dados["state"] = options["uf"].upper()[:2]
        for campo, argumento in CAMPOS_TEXTO.items():
            valor = options[argumento.lstrip("-").replace("-", "_")]
            if valor:
                dados[campo] = valor
        if criando:
            faltando = [c for c in ("name", "document") if c not in dados]
            if faltando:
                raise CommandError("Faltam --nome e/ou --cnpj para criar a transportadora.")
        return dados

    def _documento(self, valor):
        try:
            return clean_cnpj(valor)
        except ValidationError:
            return self._valida(clean_cpf, valor, "--cnpj")

    def _valida(self, funcao, valor, argumento):
        try:
            return funcao(valor)
        except ValidationError as erro:
            raise CommandError(f"{argumento}: {' '.join(erro.messages)}")

    def _slug(self, nome):
        base = slugify(nome)[:45] or "transportadora"
        slug, contador = base, 2
        while Company.objects.filter(slug=slug).exists():
            slug = f"{base}-{contador}"
            contador += 1
        return slug

    def _senha(self, informada):
        if informada:
            try:
                validate_password(informada)
            except ValidationError as erro:
                raise CommandError("Senha fraca: " + " ".join(erro.messages))
            return informada, False
        return "".join(secrets.choice(ALFABETO_SENHA) for _ in range(20)), True
