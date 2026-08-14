"""Zera a operação e deixa só o admin master, pronto para cadastrar o resto pelo painel."""

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Company, User
from core.defaults import (
    MASTER_EMAIL, MASTER_NAME, MASTER_PASSWORD, PLATFORM_CITY, PLATFORM_CNPJ,
    PLATFORM_NAME, PLATFORM_STATE,
)
from core.models import Notification
from finance.models import DriverPayout, Invoice, PricingPolicy
from operations.models import (
    ChecklistPhoto, Delivery, DeliveryEvent, Driver, DriverPing, PickupChecklist, Vehicle,
)


class Command(BaseCommand):
    help = "Apaga empresas, entregadores, frota e acessos. Recria só o admin master com o login padrão."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirma a exclusão definitiva.")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--master-email", default=MASTER_EMAIL)
        parser.add_argument("--senha", default=MASTER_PASSWORD)
        parser.add_argument("--nome", default=PLATFORM_NAME)
        parser.add_argument("--cnpj", default=PLATFORM_CNPJ)

    def handle(self, *args, **options):
        if not options["yes"] and not options["dry_run"]:
            raise CommandError("Isto apaga a operação inteira. Repita com --yes (ou use --dry-run).")

        plano = {
            "empresas": Company.objects.count(),
            "usuários": User.objects.count(),
            "entregadores": Driver.objects.count(),
            "veículos": Vehicle.objects.count(),
            "entregas": Delivery.objects.count(),
        }
        for rotulo, total in plano.items():
            self.stdout.write(f"{rotulo}: {total}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulação: nada foi apagado."))
            return

        with transaction.atomic():
            ChecklistPhoto.objects.all().delete()
            PickupChecklist.objects.all().delete()
            DriverPing.objects.all().delete()
            DeliveryEvent.objects.all().delete()
            Delivery.objects.all().update(invoice=None, payout=None)
            Invoice.objects.all().delete()
            DriverPayout.objects.all().delete()
            Delivery.objects.all().hard_delete()
            Driver.objects.all().delete()
            Vehicle.objects.all().delete()
            Notification.objects.all().delete()
            Session.objects.all().delete()
            User.objects.all().delete()
            Company.objects.all().delete()
            PricingPolicy.objects.all().delete()

        self.stdout.write(self.style.SUCCESS("Operação zerada."))
        call_command(
            "bootstrap",
            nome=options["nome"],
            cnpj=options["cnpj"],
            master_email=options["master_email"],
            master_nome=MASTER_NAME,
            senha=options["senha"],
            cidade=PLATFORM_CITY,
            uf=PLATFORM_STATE,
            stdout=self.stdout,
        )
        self.stdout.write(self.style.WARNING(
            f"Login padrão do admin master: {options['master_email']} / {options['senha']}"
        ))
        self.stdout.write("Nenhum entregador, empresa cliente ou outro acesso existe. Cadastre pelo painel.")
