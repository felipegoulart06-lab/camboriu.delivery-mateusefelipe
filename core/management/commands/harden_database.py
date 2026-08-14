from django.core.management.base import BaseCommand
from django.db import connections

from core.db_security import audit, harden


class Command(BaseCommand):
    help = "Liga RLS em todas as tabelas e tira o acesso dos papéis públicos do Supabase."

    def add_arguments(self, parser):
        parser.add_argument("--database", default="default")
        parser.add_argument("--check", action="store_true", help="Só audita, não altera nada.")

    def handle(self, *args, **options):
        connection = connections[options["database"]]
        if connection.vendor != "postgresql":
            self.stdout.write(self.style.WARNING("Banco não é PostgreSQL: nada a blindar."))
            return

        relatorio = audit(connection) if options["check"] else harden(connection)
        self.stdout.write(f"Tabelas no schema public: {relatorio['tabelas']}")

        pendencias = {
            "tabela(s) sem RLS": relatorio["sem_rls"],
            "permissão(ões) de tabela para anon/authenticated/PUBLIC": relatorio["permissoes_publicas"],
            "papel(éis) da API ainda enxergando o schema": relatorio["schema_visivel"],
            "função(ões) executável(is) pelo anon": relatorio["funcoes_expostas"],
        }
        if any(pendencias.values()):
            for rotulo, total in pendencias.items():
                if total:
                    self.stdout.write(self.style.ERROR(f"Pendência: {total} {rotulo}."))
            return

        self.stdout.write(self.style.SUCCESS(
            "Tudo com RLS ligada e sem acesso pela API pública do Supabase."
        ))
