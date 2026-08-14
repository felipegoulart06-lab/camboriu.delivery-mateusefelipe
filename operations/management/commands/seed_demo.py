import os
from datetime import date, timedelta
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from accounts.models import Company, User
from finance.models import DriverPayout, Invoice, PricingPolicy
from operations.models import Delivery, DeliveryStop, Driver, DriverPing, Vehicle


class Command(BaseCommand):
    help = "Cria ou atualiza dados seguros de demonstração para desenvolvimento."

    def add_arguments(self, parser):
        parser.add_argument("--master-email", default=os.getenv("DEMO_MASTER_EMAIL", "master@camboriudelivery.local"))
        parser.add_argument("--admin-email", default=os.getenv("DEMO_ADMIN_EMAIL", "admin@demo.local"))
        parser.add_argument("--viewer-email", default=os.getenv("DEMO_VIEWER_EMAIL", "viewer@demo.local"))
        parser.add_argument("--dispatcher-email", default=os.getenv("DEMO_DISPATCHER_EMAIL", "central@camboriudelivery.local"))
        parser.add_argument("--password", default=os.getenv("DEMO_PASSWORD", "Camboriu@123"))
        parser.add_argument("--force", action="store_true", help="Roda mesmo com DEMO_MODE desligado.")

    def handle(self, *args, **options):
        if not settings.DEMO_MODE and not options["force"]:
            # Senha conhecida e empresa fictícia não podem encostar no banco de produção.
            raise CommandError(
                "DEMO_MODE está desligado. Use `python manage.py bootstrap` para a operação real."
            )
        password = options["password"]
        platform, _ = Company.objects.update_or_create(
            slug="camboriu-delivery",
            defaults={
                "name": "Camboriú Delivery", "legal_name": "Camboriú Delivery Transportes LTDA",
                "document_type": Company.DocumentType.CNPJ, "document": "11.222.333/0001-81",
                "state_registration": "255.123.456", "tax_regime": Company.TaxRegime.SIMPLES,
                "business_area": "Transporte rodoviário de cargas", "founded_on": date(2019, 3, 12),
                "email": options["dispatcher_email"], "phone": "(47) 3333-0000",
                "contact_name": "Central de Despacho", "contact_document": "111.222.333-96",
                "contact_role": "Coordenação de operações",
                "address": "Av. do Estado, 500", "district": "Centro",
                "city": "Balneário Camboriú", "state": "SC", "zip_code": "88330-000",
                "billing_email": "financeiro@camboriudelivery.local",
                "is_platform": True, "registered_at": timezone.now(),
            },
        )
        client, _ = Company.objects.update_or_create(
            slug="demo-camboriu",
            defaults={
                "name": "Empresa Demonstração", "legal_name": "Demonstração Comércio de Insumos LTDA",
                "document_type": Company.DocumentType.CNPJ, "document": "04.512.345/0001-85",
                "state_registration": "ISENTO", "tax_regime": Company.TaxRegime.PRESUMIDO,
                "business_area": "Comércio de insumos hospitalares", "founded_on": date(2015, 8, 3),
                "email": options["admin_email"], "phone": "(47) 99999-0000", "contact_name": "Ana Operações",
                "contact_document": "555.666.777-20", "contact_role": "Gerente administrativa",
                "address": "Av. Brasil, 1000", "district": "Centro", "city": "Balneário Camboriú",
                "state": "SC", "zip_code": "88331-000", "invoice_due_day": 10,
                "billing_email": "financeiro@demo.local", "billing_phone": "(47) 3333-2200",
                "is_platform": False, "registered_at": timezone.now(),
            },
        )
        # Empresa em CPF: paga por entrega e serve para testar o bloqueio do cadastro pendente.
        pending, _ = Company.objects.update_or_create(
            slug="atelie-brisa",
            defaults={
                "name": "Ateliê Brisa", "document_type": Company.DocumentType.CPF, "document": "123.456.789-09",
                "email": "brisa@demo.local", "city": "Camboriú", "state": "SC", "is_platform": False,
                "registered_at": None,
            },
        )
        self._user(pending, "brisa@demo.local", password, User.Role.OWNER, "Brisa", "Ateliê")
        PricingPolicy.current()

        self._user(platform, options["master_email"], password, User.Role.MASTER, "Master", "Camboriú Delivery")
        admin = self._user(client, options["admin_email"], password, User.Role.ADMIN, "Ana", "Operações")
        self._user(client, options["viewer_email"], password, User.Role.VIEWER, "Vitor", "Consulta")
        self._user(platform, options["dispatcher_email"], password, User.Role.DISPATCHER, "Central", "Despacho")

        carlos_login = self._user(platform, "carlos@camboriudelivery.local", password, User.Role.DRIVER, "Carlos", "Mendes")
        mariana_login = self._user(platform, "mariana@camboriudelivery.local", password, User.Role.DRIVER, "Mariana", "Costa")
        today = timezone.localdate()
        # A busca é pelo login: assim a carga atualiza o mesmo entregador mesmo que o CPF de demonstração mude.
        carlos, _ = Driver.objects.update_or_create(
            company=platform, user=carlos_login,
            defaults={
                "cpf": "111.222.333-96",
                "name": "Carlos Mendes", "birth_date": date(1990, 5, 14),
                "rg": "4.512.336", "rg_issuer": "SSP/SC", "mother_name": "Marta Mendes",
                "phone": "(47) 99911-2200", "emergency_contact": "Marta Mendes", "emergency_phone": "(47) 99911-4400",
                "zip_code": "88330-210", "address": "Rua 1500, 220", "district": "Centro",
                "city": "Balneário Camboriú", "state": "SC",
                "cnh": "01234567890", "cnh_category": "AB", "cnh_register": "00123456789",
                "cnh_state": "SC", "cnh_issued_at": today - timedelta(days=900),
                "cnh_first_license_at": date(2010, 2, 8), "cnh_has_ear": True,
                "cnh_expires_at": today + timedelta(days=300),
                "medical_exam_expires_at": today + timedelta(days=240),
                "contract_type": Driver.Contract.EMPLOYEE, "pix_key": "111.222.333-96",
                "bank_name": "Banco do Brasil", "bank_agency": "3312", "bank_account": "18422-5",
            },
        )
        mariana, _ = Driver.objects.update_or_create(
            company=platform, user=mariana_login,
            defaults={
                "cpf": "555.666.777-20",
                "name": "Mariana Costa", "birth_date": date(1995, 11, 2),
                "rg": "5.889.114", "rg_issuer": "SSP/SC",
                "phone": "(47) 99822-3300", "emergency_contact": "João Costa", "emergency_phone": "(47) 99822-7700",
                "zip_code": "88340-100", "address": "Rua Pref. José Juvenal Mafra, 88", "district": "Centro",
                "city": "Camboriú", "state": "SC",
                "cnh": "98765432100", "cnh_category": "A", "cnh_register": "00987654321",
                "cnh_state": "SC", "cnh_issued_at": today - timedelta(days=500),
                "cnh_first_license_at": date(2016, 6, 20), "cnh_has_ear": True,
                "cnh_expires_at": today + timedelta(days=700),
                "medical_exam_expires_at": today + timedelta(days=400),
                "contract_type": Driver.Contract.PARTNER, "pix_key": "mariana@camboriudelivery.local",
            },
        )
        moto, _ = Vehicle.objects.update_or_create(
            company=platform, plate="ABC1D23",
            defaults={
                "kind": Vehicle.Kind.MOTORCYCLE, "plate_state": "SC", "renavam": "12345678900",
                "chassis": "9C2KC2200PR000123", "brand": "Honda", "model": "CG 160 Cargo",
                "year": 2025, "model_year": 2025, "color": "Vermelha", "fuel": Vehicle.Fuel.FLEX,
                "mileage_km": 18400, "capacity_kg": Decimal("25"), "equipment": "Baú térmico 90L",
                "top_case_liters": 90, "lockable": True,
                "owner_name": "Camboriú Delivery Transportes LTDA", "owner_document": "11.222.333/0001-81",
                "crlv_expires_at": today + timedelta(days=180),
                "has_tracker": True, "tracker_provider": "Sascar",
            },
        )
        fiorino, _ = Vehicle.objects.update_or_create(
            company=platform, plate="DEF4G56",
            defaults={
                "kind": Vehicle.Kind.CAR, "plate_state": "SC", "renavam": "98765432103",
                "chassis": "9BD25519MC1000456", "brand": "Fiat", "model": "Fiorino",
                "year": 2024, "model_year": 2024, "color": "Branca", "fuel": Vehicle.Fuel.FLEX,
                "mileage_km": 42300, "capacity_kg": Decimal("500"), "equipment": "Compartimento lacrado",
                "doors": 3, "cargo_length_cm": 170, "cargo_width_cm": 140, "cargo_height_cm": 120,
                "lockable": True,
                "owner_name": "Camboriú Delivery Transportes LTDA", "owner_document": "11.222.333/0001-81",
                "crlv_expires_at": today + timedelta(days=210),
                "insurer": "Porto Seguro", "insurance_policy": "AP-778931",
                "insurance_expires_at": today + timedelta(days=150),
                "has_tracker": True, "tracker_provider": "Sascar",
            },
        )

        samples = [
            ("Clínica Atlântico", Delivery.ItemType.SAMPLE, Delivery.Priority.CRITICAL, Delivery.Status.PICKUP, carlos, moto),
            ("Silva & Ramos Advocacia", Delivery.ItemType.DOCUMENT, Delivery.Priority.URGENT, Delivery.Status.DISPATCHING, mariana, moto),
            ("Farmácia Central", Delivery.ItemType.MEDICINE, Delivery.Priority.NORMAL, Delivery.Status.DELIVERED, carlos, fiorino),
            ("Joalheria Costa", Delivery.ItemType.HIGH_VALUE, Delivery.Priority.URGENT, Delivery.Status.REQUESTED, None, None),
        ]
        for index, (requester, item, priority, status, driver, vehicle) in enumerate(samples):
            delivery, created = Delivery.objects.update_or_create(
                company=client, requester=requester,
                defaults={
                    "item_type": item,
                    "description": f"Entrega demonstrativa para {requester}.",
                    "declared_value": Decimal("350.00"),
                    "confidential": item in {Delivery.ItemType.SAMPLE, Delivery.ItemType.HIGH_VALUE},
                    "pickup_address": "Av. Brasil, 1000, Centro, Balneário Camboriú",
                    "pickup_contact": "Recepção · (47) 3333-1000",
                    "pickup_lat": -26.9906, "pickup_lng": -48.6349,
                    "delivery_address": f"Rua das Flores, {120 + index}, Camboriú",
                    "delivery_contact": "Responsável · (47) 99999-1000",
                    "delivery_lat": -27.0247, "delivery_lng": -48.6541,
                    "pickup_window": timezone.now() + timedelta(hours=index),
                    "deadline": timezone.now() + timedelta(hours=index + 3),
                    "priority": priority, "status": status, "driver": driver, "vehicle": vehicle,
                },
            )
            if created:
                delivery.register_event("Entrega criada pela carga demo", admin)
            if index == 0 and not delivery.stops.exists():
                DeliveryStop.objects.create(
                    delivery=delivery, order=2, address="Rua 3000, 45, Centro, Balneário Camboriú",
                    contact="Laboratório Sul · (47) 3333-4400", notes="Entregar na recepção do 2º andar",
                )
                DeliveryStop.objects.create(
                    delivery=delivery, order=3, address="Rua Pref. José Juvenal Mafra, 210, Camboriú",
                    contact="Unidade Camboriú · (47) 3333-5500",
                )
            PricingPolicy.current().apply_to(delivery)

        self._drop_unused_client_fleet(client)
        self._demo_trail(carlos)
        self._demo_finance(client, carlos)
        self.stdout.write(self.style.SUCCESS(f"1) Admin master:      {options['master_email']} / {password}"))
        self.stdout.write(self.style.SUCCESS(f"   Central (despacho): {options['dispatcher_email']} / {password}"))
        self.stdout.write(self.style.SUCCESS(f"2) Empresa cliente:   {options['admin_email']} / {password}"))
        self.stdout.write(self.style.SUCCESS(f"   Empresa sem cadastro: brisa@demo.local / {password}"))
        self.stdout.write(self.style.SUCCESS(f"3) Entregadores:      carlos@camboriudelivery.local e mariana@camboriudelivery.local / {password}"))

    def _demo_finance(self, client, driver):
        """Uma fatura em aberto e um repasse pago para o painel contábil já abrir com números."""
        billable = Delivery.objects.filter(company=client, status=Delivery.Status.DELIVERED, invoice__isnull=True).exclude(price=0)
        if billable.exists() and not Invoice.objects.filter(company=client).exists():
            invoice = Invoice.create_for(client, billable, timezone.localdate() + timedelta(days=10))
            invoice.bank_slip_line = "34191.79001 01043.510047 91020.150008 9 12340000012345"
            invoice.status = Invoice.Status.ISSUED
            invoice.issued_at = timezone.now()
            invoice.save(update_fields=["bank_slip_line", "status", "issued_at"])

        paid = Delivery.objects.filter(driver=driver, status=Delivery.Status.DELIVERED, payout__isnull=True)
        if paid.exists() and not DriverPayout.objects.filter(driver=driver).exists():
            today = timezone.localdate()
            payout = DriverPayout.create_for(driver, paid, today.replace(day=1), today)
            payout.mark_paid("Pix")

    def _demo_trail(self, driver):
        """Posições fictícias para o mapa da empresa já abrir com o entregador em rota."""
        delivery = Delivery.objects.filter(driver=driver, status__in=Delivery.TRACKABLE_STATUSES).first()
        if not delivery or DriverPing.objects.filter(delivery=delivery).exists():
            return
        route = [(-27.0075, -48.6180), (-27.0012, -48.6244), (-26.9958, -48.6301), (-26.9921, -48.6338)]
        for lat, lng in route:
            DriverPing.objects.create(driver=driver, delivery=delivery, lat=lat, lng=lng, accuracy=12)
        driver.register_position(*route[-1])

    def _drop_unused_client_fleet(self, client):
        """Cargas antigas colocavam a frota na empresa cliente; agora ela é da plataforma."""
        Driver.objects.filter(company=client, delivery__isnull=True, checklists__isnull=True).delete()
        Vehicle.objects.filter(company=client, delivery__isnull=True).delete()

    def _user(self, company, email, password, role, first_name, last_name):
        user, _ = User.objects.get_or_create(username=email, defaults={"email": email})
        user.company, user.role, user.first_name, user.last_name, user.is_active = company, role, first_name, last_name, True
        user.email = email
        user.set_password(password)
        user.save()
        return user
