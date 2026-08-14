from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import Company, User
from core.models import Notification
from finance.models import DriverPayout, Invoice
from operations.models import (
    ChecklistPhoto, Delivery, DeliveryEvent, Driver, DriverPing, PickupChecklist, Vehicle,
)

# Tudo o que o antigo `seed_demo` criava. É por esta lista que a limpeza se guia.
DEMO_COMPANY_SLUGS = ("demo-camboriu", "atelie-brisa")
DEMO_USERNAMES = (
    "master@camboriudelivery.local",
    "central@camboriudelivery.local",
    "carlos@camboriudelivery.local",
    "mariana@camboriudelivery.local",
    "admin@demo.local",
    "viewer@demo.local",
    "brisa@demo.local",
)
DEMO_PLATES = ("ABC1D23", "DEF4G56")


class Command(BaseCommand):
    help = "Apaga os dados de demonstração (empresas, entregadores, frota e entregas fictícias)."

    def add_arguments(self, parser):
        parser.add_argument("--yes", action="store_true", help="Confirma a exclusão definitiva.")
        parser.add_argument("--dry-run", action="store_true", help="Mostra o que seria apagado.")

    def handle(self, *args, **options):
        if not options["yes"] and not options["dry_run"]:
            raise CommandError("Isto apaga dados de forma definitiva. Repita com --yes (ou use --dry-run).")

        companies = Company.objects.filter(slug__in=DEMO_COMPANY_SLUGS)
        platform = Company.objects.platform()
        users = User.objects.filter(username__in=DEMO_USERNAMES) | User.objects.filter(company__in=companies)
        drivers = Driver.objects.filter(company__in=companies) | Driver.objects.filter(user__in=users)
        vehicles = Vehicle.objects.filter(company__in=companies)
        if platform:
            vehicles = vehicles | Vehicle.objects.filter(company=platform, plate__in=DEMO_PLATES)
        deliveries = (
            Delivery.objects.filter(company__in=companies)
            | Delivery.objects.filter(driver__in=drivers)
            | Delivery.objects.filter(vehicle__in=vehicles)
        )

        plano = {
            "entregas": deliveries.distinct().count(),
            "entregadores": drivers.distinct().count(),
            "veículos": vehicles.distinct().count(),
            "empresas": companies.count(),
            "usuários": users.distinct().count(),
        }
        for rotulo, total in plano.items():
            self.stdout.write(f"{rotulo}: {total}")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Simulação: nada foi apagado."))
            return
        if not any(plano.values()):
            self.stdout.write(self.style.SUCCESS("Nenhum dado de demonstração encontrado."))
            return

        delivery_ids = list(deliveries.distinct().values_list("pk", flat=True))
        driver_ids = list(drivers.distinct().values_list("pk", flat=True))
        vehicle_ids = list(vehicles.distinct().values_list("pk", flat=True))
        user_ids = list(users.distinct().values_list("pk", flat=True))
        company_ids = list(companies.values_list("pk", flat=True))

        with transaction.atomic():
            checklists = PickupChecklist.objects.filter(driver_id__in=driver_ids) | PickupChecklist.objects.filter(
                delivery_id__in=delivery_ids
            )
            checklist_ids = list(checklists.distinct().values_list("pk", flat=True))
            ChecklistPhoto.objects.filter(checklist_id__in=checklist_ids).delete()
            PickupChecklist.objects.filter(pk__in=checklist_ids).delete()
            DriverPing.objects.filter(delivery_id__in=delivery_ids).delete()
            DriverPing.objects.filter(driver_id__in=driver_ids).delete()
            DeliveryEvent.objects.filter(delivery_id__in=delivery_ids).delete()
            # Solta as entregas das faturas e repasses antes de apagar os dois lados.
            Delivery.objects.filter(pk__in=delivery_ids).update(invoice=None, payout=None)
            Invoice.objects.filter(company_id__in=company_ids).delete()
            DriverPayout.objects.filter(driver_id__in=driver_ids).delete()
            Delivery.objects.filter(pk__in=delivery_ids).hard_delete()

            Driver.objects.filter(pk__in=driver_ids).delete()
            Vehicle.objects.filter(pk__in=vehicle_ids).delete()
            Notification.objects.filter(company_id__in=company_ids).delete()
            User.objects.filter(pk__in=user_ids).delete()
            Company.objects.filter(pk__in=company_ids).delete()

        self.stdout.write(self.style.SUCCESS("Dados de demonstração removidos."))
        self.stdout.write("Use `python manage.py bootstrap` para criar a operação real.")
