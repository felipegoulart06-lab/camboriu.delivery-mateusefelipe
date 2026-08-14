import io
import shutil
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from accounts.models import Company, User
from core.models import Notification
from finance.models import PricingPolicy

from .models import ChecklistPhoto, Delivery, DeliveryStop, Driver, DriverPing, PickupChecklist, Vehicle

EMPTY_STOPS = {"stops-TOTAL_FORMS": "0", "stops-INITIAL_FORMS": "0", "stops-MIN_NUM_FORMS": "0", "stops-MAX_NUM_FORMS": "9"}

MEDIA_FOR_TESTS = tempfile.mkdtemp(prefix="camboriu-tests-")


def fake_photo(name="foto.jpg"):
    buffer = io.BytesIO()
    Image.new("RGB", (12, 12), "#0f7866").save(buffer, format="JPEG")
    return SimpleUploadedFile(name, buffer.getvalue(), content_type="image/jpeg")


def fake_document(name="documento.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4 documento de teste", content_type="application/pdf")


def vehicle_payload(**extra):
    """Ficha mínima aceita pelo cadastro de veículo, já com os anexos obrigatórios."""
    payload = {
        "kind": Vehicle.Kind.CAR, "plate": "NEW1A23", "plate_state": "SC",
        "renavam": "11122233307", "chassis": "9BD25519MC1000456",
        "brand": "Fiat", "model": "Uno", "year": 2024, "model_year": 2024,
        "color": "Branco", "fuel": Vehicle.Fuel.FLEX, "mileage_km": 12000,
        "owner_name": "Empresa A", "owner_document": "44.555.666/0001-81",
        "crlv_expires_at": (timezone.localdate() + timedelta(days=120)).isoformat(),
        "status": Vehicle.Status.AVAILABLE, "capacity_kg": "500",
        "insurer": "Porto Seguro", "insurance_policy": "AP-1", "doors": 3,
        "insurance_expires_at": (timezone.localdate() + timedelta(days=200)).isoformat(),
        "crlv_document": fake_document(), "photo_front": fake_photo(), "photo_plate": fake_photo(),
        "insurance_document": fake_document(),
    }
    payload.update(extra)
    return payload


def driver_payload(**extra):
    """Ficha mínima aceita pelo cadastro de entregador, com CNH e comprovantes."""
    today = timezone.localdate()
    payload = {
        "name": "Bruno Lima", "cpf": "321.654.987-91", "birth_date": "1992-04-10",
        "rg": "3.998.221", "rg_issuer": "SSP/SC", "phone": "(47) 99700-1122",
        "emergency_contact": "Ana Lima", "emergency_phone": "(47) 99700-3344",
        "zip_code": "88330-100", "address": "Rua 1500, 200", "district": "Centro",
        "city": "Balneário Camboriú", "state": "SC",
        "cnh": "55544433322", "cnh_category": "A", "cnh_state": "SC",
        "cnh_issued_at": (today - timedelta(days=400)).isoformat(),
        "cnh_expires_at": (today + timedelta(days=400)).isoformat(),
        "medical_exam_expires_at": (today + timedelta(days=200)).isoformat(),
        "cnh_has_ear": "on", "contract_type": Driver.Contract.PARTNER,
        "status": Driver.Status.ACTIVE, "pix_key": "321.654.987-91", "notes": "",
        "cnh_front": fake_photo(), "proof_of_address": fake_document(), "portrait": fake_photo(),
    }
    payload.update(extra)
    return payload


def make_company(name, slug, document, **extra):
    """Empresa já com o cadastro concluído: o painel só libera as telas depois disso."""
    extra.setdefault("registered_at", timezone.now())
    return Company.objects.create(name=name, slug=slug, document=document, **extra)


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class OperationsTestCase(TestCase):
    def setUp(self):
        self.platform = make_company("Camboriú Delivery", "plataforma", "11", is_platform=True)
        self.a = make_company("Empresa A", "a", "1")
        self.b = make_company("Empresa B", "b", "2")
        self.admin = User.objects.create_user("admin-a", password="test-pass-123", company=self.a, role=User.Role.ADMIN)
        self.viewer = User.objects.create_user("viewer-a", password="test-pass-123", company=self.a, role=User.Role.VIEWER)
        self.master = User.objects.create_user("master", password="test-pass-123", company=self.platform, role=User.Role.MASTER)
        self.dispatcher = User.objects.create_user("central", password="test-pass-123", company=self.platform, role=User.Role.DISPATCHER)
        self.driver_login = User.objects.create_user("carlos", password="test-pass-123", company=self.platform, role=User.Role.DRIVER)
        self.fleet_driver = Driver.objects.create(company=self.platform, user=self.driver_login, name="Carlos", cpf="9", cnh="9", cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE)
        self.driver_b = Driver.objects.create(company=self.b, name="Motorista B", cpf="2", cnh="2", cnh_category="A", phone="2", contract_type=Driver.Contract.EMPLOYEE)
        self.vehicle = Vehicle.objects.create(company=self.platform, kind=Vehicle.Kind.MOTORCYCLE, plate="AAA1A11", brand="Honda", model="CG", year=2025)
        self.delivery = self._delivery(self.a, "Cliente A")
        self.delivery_b = self._delivery(self.b, "Cliente B")

    def _delivery(self, company, requester, **extra):
        return Delivery.objects.create(
            company=company, requester=requester, item_type=Delivery.ItemType.DOCUMENT, description="Teste",
            pickup_address="Av. Brasil, 1000", pickup_contact="Recepção", delivery_address="Rua das Flores, 10",
            delivery_contact="Responsável", **extra,
        )


class TenantSecurityTests(OperationsTestCase):
    def test_list_and_detail_are_isolated_by_company(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("delivery_list"))
        self.assertNotContains(response, self.delivery_b.code)
        self.assertEqual(self.client.get(reverse("delivery_detail", args=[self.delivery_b.pk])).status_code, 404)

    def test_cross_company_driver_is_rejected(self):
        self.delivery.driver = self.driver_b
        with self.assertRaises(ValidationError):
            self.delivery.save()

    def test_platform_fleet_driver_is_accepted(self):
        self.delivery.driver = self.fleet_driver
        self.delivery.save()
        self.assertEqual(self.delivery.driver.company, self.platform)

    def test_viewer_cannot_create_or_edit(self):
        self.client.force_login(self.viewer)
        self.assertRedirects(self.client.get(reverse("delivery_create")), reverse("dashboard"))
        self.assertRedirects(self.client.get(reverse("driver_create")), reverse("dashboard"))

    def test_admin_can_create_resource_for_own_company(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("vehicle_create"), vehicle_payload())
        self.assertRedirects(response, reverse("vehicle_list"))
        self.assertTrue(Vehicle.objects.filter(company=self.a, plate="NEW1A23").exists())

    def test_company_request_never_sets_driver_or_status(self):
        self.client.force_login(self.admin)
        response = self.client.post(reverse("delivery_create"), {
            "requester": "Clínica", "item_type": "sample", "description": "Amostra", "declared_value": "10",
            "pickup_address": "A", "pickup_contact": "A", "delivery_address": "B", "delivery_contact": "B",
            "priority": "urgent", "driver": self.fleet_driver.pk, "status": Delivery.Status.DELIVERED,
            **EMPTY_STOPS,
        })
        created = Delivery.objects.get(company=self.a, requester="Clínica")
        self.assertRedirects(response, reverse("delivery_detail", args=[created.pk]))
        self.assertEqual(created.status, Delivery.Status.REQUESTED)
        self.assertIsNone(created.driver)


class VehicleRegistrationTests(OperationsTestCase):
    """Moto, carro e utilitário cobram dados diferentes na mesma ficha."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.master)
        self.url = reverse("vehicle_create")

    def test_car_requires_insurance_and_documents(self):
        payload = vehicle_payload()
        for field in ("insurer", "insurance_policy", "insurance_expires_at", "crlv_document", "photo_front"):
            payload.pop(field)
        response = self.client.post(self.url, payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "obrigatório para carro")
        self.assertContains(response, "Envie este documento")
        self.assertFalse(Vehicle.objects.filter(plate="NEW1A23").exists())

    def test_utility_requires_body_type_and_cargo_size(self):
        payload = vehicle_payload(kind=Vehicle.Kind.UTILITY, plate="UTI2B34")
        response = self.client.post(self.url, payload)
        self.assertContains(response, "obrigatório para utilitário")

        response = self.client.post(self.url, vehicle_payload(
            kind=Vehicle.Kind.UTILITY, plate="UTI2B34", body_type=Vehicle.Body.VAN,
            gross_weight_kg="3500", cargo_length_cm=250, cargo_width_cm=160, cargo_height_cm=180,
            photo_cargo=fake_photo(),
        ))
        self.assertRedirects(response, reverse("vehicle_list"))
        vehicle = Vehicle.objects.get(plate="UTI2B34")
        self.assertEqual(vehicle.cargo_volume_liters, 7200)

    def test_motorcycle_requires_the_top_case_but_not_the_insurance(self):
        payload = vehicle_payload(kind=Vehicle.Kind.MOTORCYCLE, plate="MOT3C45", capacity_kg="25")
        for field in ("insurer", "insurance_policy", "insurance_expires_at", "insurance_document", "doors"):
            payload.pop(field)
        response = self.client.post(self.url, payload)
        self.assertContains(response, "obrigatório para moto")

        payload = vehicle_payload(kind=Vehicle.Kind.MOTORCYCLE, plate="MOT3C45", capacity_kg="25", top_case_liters=90)
        for field in ("insurer", "insurance_policy", "insurance_expires_at", "insurance_document", "doors"):
            payload.pop(field)
        self.assertRedirects(self.client.post(self.url, payload), reverse("vehicle_list"))

    def test_plate_renavam_and_chassis_are_checked(self):
        response = self.client.post(self.url, vehicle_payload(plate="12345", renavam="123", chassis="ABC"))
        self.assertContains(response, "Placa inválida")
        self.assertContains(response, "RENAVAM inválido")
        self.assertContains(response, "Chassi inválido")

    def test_documents_are_served_only_to_the_owner(self):
        self.client.post(self.url, vehicle_payload())
        vehicle = Vehicle.objects.get(plate="NEW1A23")
        self.assertEqual(self.client.get(reverse("vehicle_document", args=[vehicle.pk, "crlv_document"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("vehicle_document", args=[vehicle.pk, "photo_rear"])).status_code, 404)

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("vehicle_document", args=[vehicle.pk, "crlv_document"])).status_code, 404)


class DriverRegistrationTests(OperationsTestCase):
    """A ficha do entregador cobra CNH válida, comprovantes e forma de repasse."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.master)
        self.url = reverse("platform_driver_create")

    def base(self, **extra):
        return driver_payload(email="bruno@camboriudelivery.local", password1="Entrega@2026", password2="Entrega@2026", **extra)

    def test_expired_cnh_and_missing_ear_block_the_registration(self):
        payload = self.base(cnh_expires_at=(timezone.localdate() - timedelta(days=1)).isoformat())
        payload.pop("cnh_has_ear")
        response = self.client.post(self.url, payload)
        self.assertContains(response, "está vencida")
        self.assertContains(response, "EAR")
        self.assertFalse(Driver.objects.filter(cpf="321.654.987-91").exists())

    def test_invalid_cpf_and_missing_documents_are_reported(self):
        payload = self.base(cpf="111.111.111-11")
        for field in ("cnh_front", "proof_of_address", "portrait"):
            payload.pop(field)
        response = self.client.post(self.url, payload)
        self.assertContains(response, "CPF inválido")
        self.assertContains(response, "Envie este documento")

    def test_payout_needs_pix_or_full_bank_data(self):
        payload = self.base()
        payload.pop("pix_key")
        self.assertContains(self.client.post(self.url, payload), "chave Pix")

        payload = self.base(bank_name="Banco do Brasil", bank_agency="3312", bank_account="18422-5")
        payload.pop("pix_key")
        self.assertRedirects(self.client.post(self.url, payload), reverse("platform_drivers"))

    def test_documents_are_saved_and_served_to_the_master(self):
        self.client.post(self.url, self.base())
        driver = Driver.objects.get(cpf="321.654.987-91")
        self.assertFalse(driver.missing_documents)
        self.assertEqual(driver.full_address, "Rua 1500, 200 · Centro · Balneário Camboriú/SC")
        self.assertEqual(self.client.get(reverse("driver_document", args=[driver.pk, "cnh_front"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("driver_document", args=[driver.pk, "criminal_record"])).status_code, 404)


class DispatchTests(OperationsTestCase):
    def test_board_shows_requests_from_every_company(self):
        self.client.force_login(self.dispatcher)
        response = self.client.get(reverse("dispatch_board"))
        self.assertContains(response, self.delivery.code)
        self.assertContains(response, self.delivery_b.code)

    def test_company_user_cannot_open_dispatch_board(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("dispatch_board")), reverse("dashboard"))

    def test_dispatch_assigns_driver_and_notifies_company(self):
        self.client.force_login(self.dispatcher)
        response = self.client.post(reverse("dispatch_delivery", args=[self.delivery.pk]), {"driver": self.fleet_driver.pk, "vehicle": self.vehicle.pk})
        self.assertRedirects(response, reverse("dispatch_detail", args=[self.delivery.pk]))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.DISPATCHING)
        self.assertEqual(self.delivery.driver, self.fleet_driver)
        self.assertIsNotNone(self.delivery.dispatched_at)

    def test_driver_without_login_cannot_be_dispatched(self):
        no_login = Driver.objects.create(company=self.platform, name="Sem acesso", cpf="77", cnh="77", cnh_category="A", phone="7", contract_type=Driver.Contract.PARTNER)
        self.client.force_login(self.dispatcher)
        response = self.client.post(reverse("dispatch_delivery", args=[self.delivery.pk]), {"driver": no_login.pk})
        self.assertContains(response, "ainda não tem login")
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.REQUESTED)

    def test_cancel_without_confirmation_keeps_the_request(self):
        self.client.force_login(self.dispatcher)
        self.client.post(reverse("dispatch_cancel", args=[self.delivery.pk]), {"reason": "teste"})
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.REQUESTED)

    def test_cancel_with_confirmation_keeps_the_record(self):
        self.client.force_login(self.dispatcher)
        self.client.post(reverse("dispatch_cancel", args=[self.delivery.pk]), {"reason": "cliente desistiu", "confirm": "1"})
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.CANCELED)
        self.assertTrue(Delivery.objects.filter(pk=self.delivery.pk).exists())

    def test_company_request_cannot_be_deleted(self):
        from django.db.models.deletion import ProtectedError
        with self.assertRaises(ProtectedError):
            self.delivery.delete()
        with self.assertRaises(ProtectedError):
            Delivery.objects.filter(pk=self.delivery.pk).delete()
        with self.assertRaises(ProtectedError):
            self.a.delivery_set.all().delete()
        self.assertTrue(Delivery.objects.filter(pk=self.delivery.pk).exists())

    def test_admin_cannot_delete_a_company_request(self):
        root = User.objects.create_superuser("root", "root@test.local", "test-pass-123", company=self.platform, role=User.Role.MASTER)
        self.client.force_login(root)
        response = self.client.get(reverse("admin:operations_delivery_delete", args=[self.delivery.pk]))
        self.assertEqual(response.status_code, 403)


class MasterAccountTests(OperationsTestCase):
    """As três contas: admin master, empresa contratante e entregador."""

    def test_master_registers_a_company_and_its_first_login(self):
        self.client.force_login(self.master)
        response = self.client.post(reverse("company_create"), {
            "name": "Padaria do Porto", "legal_name": "Padaria do Porto LTDA",
            "document_type": Company.DocumentType.CNPJ, "document": "44555666000181",
            "state_registration": "ISENTO", "tax_regime": Company.TaxRegime.SIMPLES,
            "business_area": "Panificação", "founded_on": "2018-02-01",
            "email": "contato@padaria.local", "phone": "(47) 3300-1234", "contact_name": "Rita Souza",
            "contact_document": "987.654.321-00", "contact_role": "Sócia",
            "zip_code": "88330-100", "address": "Rua 1500, 200", "district": "Centro",
            "city": "Balneário Camboriú", "state": "SC", "invoice_due_day": "15",
            "billing_email": "financeiro@padaria.local",
            "is_active": "on", "notes": "",
        })
        company = Company.objects.get(document="44.555.666/0001-81")
        self.assertEqual(company.slug, "padaria-do-porto")
        self.assertRedirects(response, reverse("company_user_create", args=[company.pk]))

        self.client.post(reverse("company_user_create", args=[company.pk]), {
            "email": "Rita@Padaria.local", "first_name": "Rita", "last_name": "Souza",
            "role": User.Role.ADMIN, "is_active": "on",
            "password1": "Padaria@2026", "password2": "Padaria@2026",
        })
        account = User.objects.get(username="rita@padaria.local")
        self.assertEqual(account.company, company)
        self.assertTrue(self.client.login(username="rita@padaria.local", password="Padaria@2026"))

    def test_master_creates_driver_with_app_login(self):
        self.client.force_login(self.master)
        self.client.post(reverse("platform_driver_create"), driver_payload(
            email="bruno@camboriudelivery.local", password1="Entrega@2026", password2="Entrega@2026",
        ))
        driver = Driver.objects.get(cpf="321.654.987-91")
        self.assertEqual(driver.company, self.platform)
        self.assertEqual(driver.user.role, User.Role.DRIVER)
        self.assertTrue(self.client.login(username="bruno@camboriudelivery.local", password="Entrega@2026"))
        self.assertEqual(self.client.get(reverse("driver_home")).status_code, 200)

    def test_only_master_manages_companies(self):
        self.client.force_login(self.dispatcher)
        self.assertRedirects(self.client.get(reverse("company_list")), reverse("platform_home"))
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("company_list")), reverse("dashboard"))

    def test_suspend_without_confirmation_keeps_the_company_active(self):
        self.client.force_login(self.master)
        self.client.post(reverse("company_toggle", args=[self.a.pk]))
        self.a.refresh_from_db()
        self.assertTrue(self.a.is_active)

    def test_suspended_company_cannot_log_in(self):
        self.client.force_login(self.master)
        self.client.post(reverse("company_toggle", args=[self.a.pk]), {"confirm": "1"})
        self.a.refresh_from_db()
        self.assertFalse(self.a.is_active)

        self.client.logout()
        response = self.client.post(reverse("login"), {"username": "admin-a", "password": "test-pass-123"})
        self.assertContains(response, "suspenso")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_each_account_lands_on_its_own_panel(self):
        from core.auth_views import home_for
        for user, expected in ((self.master, "platform_home"), (self.dispatcher, "platform_home"), (self.admin, "dashboard"), (self.driver_login, "driver_home")):
            self.assertEqual(home_for(user), reverse(expected))
            self.client.force_login(user)
            response = self.client.get(reverse("login"))
            self.assertContains(response, "Você já está logado")
            self.assertContains(response, reverse(expected))
            self.client.logout()

    @override_settings(DEMO_MODE=True)
    def test_switch_account_logs_out_and_prepares_the_next_login(self):
        """Atalho de troca de conta: só existe no modo demonstração."""
        self.client.force_login(self.admin)
        response = self.client.post(reverse("switch_account"), {"perfil": "entregador"})
        self.assertRedirects(response, f"{reverse('login')}?perfil=entregador&trocar=1")
        self.assertNotIn("_auth_user_id", self.client.session)
        login_page = self.client.get(response.url)
        self.assertContains(login_page, "carlos@camboriudelivery.local")

    def test_platform_staff_opens_the_integration_manual_and_downloads_the_pdf(self):
        self.client.force_login(self.master)
        page = self.client.get(reverse("platform_integration"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Integrações")
        self.assertContains(page, "12 fotos")
        self.assertContains(page, reverse("platform_integration_pdf"))
        self.assertContains(page, "Fachada ou recepção")

        pdf = self.client.get(reverse("platform_integration_pdf"))
        self.assertEqual(pdf.status_code, 200)
        self.assertEqual(pdf["Content-Type"], "application/pdf")
        body = b"".join(pdf.streaming_content)
        self.assertTrue(body.startswith(b"%PDF"))

    def test_company_cannot_open_integration(self):
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.client.get(reverse("platform_integration")).status_code, 200)
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("platform_integration")), reverse("dashboard"))


class CompanyRegistrationTests(OperationsTestCase):
    """O cadastro da empresa é primordial: sem ele o painel fica bloqueado."""

    def setUp(self):
        super().setUp()
        self.fresh = Company.objects.create(name="Sem cadastro", slug="sem-cadastro", document="90")
        self.owner = User.objects.create_user("dono", password="test-pass-123", company=self.fresh, role=User.Role.OWNER)

    def test_panel_is_blocked_until_the_company_finishes_its_registration(self):
        self.client.force_login(self.owner)
        for name in ("dashboard", "delivery_list", "delivery_create"):
            self.assertRedirects(self.client.get(reverse(name)), reverse("company_profile"))

    def profile_payload(self, **extra):
        payload = {
            "name": "Ateliê Brisa", "legal_name": "Brisa Confecções ME",
            "document_type": Company.DocumentType.MEI, "document": "12345678000195",
            "state_registration": "ISENTO", "tax_regime": Company.TaxRegime.MEI,
            "business_area": "Confecção sob medida", "founded_on": "2021-09-15",
            "contact_name": "Bia Brisa", "contact_document": "987.654.321-00", "contact_role": "Titular",
            "email": "bia@brisa.local", "phone": "(47) 99888-1122",
            "zip_code": "88340-000", "address": "Rua 500, 90",
            "district": "Centro", "city": "Camboriú", "state": "SC", "invoice_due_day": "20",
            "billing_email": "bia@brisa.local",
            "document_file": fake_document(), "articles_of_association": fake_document(),
            "address_proof": fake_document(), "contact_document_file": fake_photo(),
        }
        payload.update(extra)
        return payload

    def test_registration_form_releases_the_panel_and_warns_the_master(self):
        self.client.force_login(self.owner)
        response = self.client.post(reverse("company_profile"), self.profile_payload())
        self.assertRedirects(response, reverse("dashboard"))
        self.fresh.refresh_from_db()
        self.assertTrue(self.fresh.is_registered)
        self.assertTrue(self.fresh.can_invoice)
        self.assertEqual(self.fresh.document, "12.345.678/0001-95")
        self.assertFalse(self.fresh.missing_documents)
        self.assertEqual(self.client.get(reverse("delivery_list")).status_code, 200)
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.COMPANY_REGISTERED, company=self.fresh).exists())

    def test_registration_requires_the_documents_and_a_valid_cnpj(self):
        self.client.force_login(self.owner)
        payload = self.profile_payload(document="12345678000100")
        for field in ("document_file", "articles_of_association", "address_proof", "contact_document_file"):
            payload.pop(field)
        response = self.client.post(reverse("company_profile"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "CNPJ inválido")
        self.assertContains(response, "Envie este documento")
        self.fresh.refresh_from_db()
        self.assertFalse(self.fresh.is_registered)

    def test_own_documents_are_served_only_to_the_company(self):
        self.client.force_login(self.owner)
        self.client.post(reverse("company_profile"), self.profile_payload())
        self.assertEqual(self.client.get(reverse("company_own_document", args=["address_proof"])).status_code, 200)
        self.assertEqual(self.client.get(reverse("company_own_document", args=["senha"])).status_code, 404)

        self.client.force_login(self.master)
        self.assertEqual(self.client.get(reverse("company_document", args=[self.fresh.pk, "address_proof"])).status_code, 200)

    def test_cpf_registration_cannot_invoice(self):
        self.fresh.document_type = Company.DocumentType.CPF
        self.assertFalse(self.fresh.can_invoice)


class MultiStopTests(OperationsTestCase):
    def test_company_creates_a_trip_with_three_destinations_and_gets_priced(self):
        self.client.force_login(self.admin)
        policy = PricingPolicy.current()
        response = self.client.post(reverse("delivery_create"), {
            "requester": "Distribuidora Sul", "item_type": "document", "description": "Três pontos",
            "declared_value": "0", "pickup_address": "Av. Brasil, 1000", "pickup_contact": "Recepção",
            "delivery_address": "Rua A, 1", "delivery_contact": "Ponto 1", "priority": "normal",
            "stops-TOTAL_FORMS": "3", "stops-INITIAL_FORMS": "0", "stops-MIN_NUM_FORMS": "0", "stops-MAX_NUM_FORMS": "9",
            "stops-0-address": "Rua B, 2", "stops-0-contact": "Ponto 2", "stops-0-notes": "",
            "stops-1-address": "Rua C, 3", "stops-1-contact": "Ponto 3", "stops-1-notes": "",
            "stops-2-address": "", "stops-2-contact": "", "stops-2-notes": "",
        })
        created = Delivery.objects.get(requester="Distribuidora Sul")
        self.assertRedirects(response, reverse("delivery_detail", args=[created.pk]))
        self.assertEqual(created.destination_count, 3)
        self.assertEqual([stop.order for stop in created.destinations], [1, 2, 3])
        self.assertEqual(created.price, policy.base_price + policy.price_per_extra_stop * 2)
        self.assertEqual(created.driver_payout_amount, policy.driver_share(created.price))

    def test_request_notifies_the_master_with_the_company_registration_data(self):
        self.a.legal_name = "Empresa A Comércio LTDA"
        self.a.document = "12.345.678/0001-00"
        self.a.save()
        self.client.force_login(self.admin)
        self.client.post(reverse("delivery_create"), {
            "requester": "Clínica", "item_type": "sample", "description": "Amostra", "declared_value": "0",
            "pickup_address": "A", "pickup_contact": "A", "delivery_address": "B", "delivery_contact": "B",
            "priority": "normal", **EMPTY_STOPS,
        })
        notification = Notification.objects.filter(kind=Notification.Kind.DELIVERY_REQUEST).latest("created_at")
        self.assertEqual(notification.company, self.a)
        self.assertIn("Empresa A Comércio LTDA", notification.body)
        self.assertIn("12.345.678/0001-00", notification.body)

    def test_request_pdf_carries_the_company_header(self):
        DeliveryStop.objects.create(delivery=self.delivery, order=2, address="Rua B, 2", contact="Ponto 2")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("company_delivery_document", args=[self.delivery.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(b"%PDF" in b"".join(response.streaming_content)[:2048])

    def test_other_company_cannot_download_the_pdf(self):
        outsider = User.objects.create_user("admin-b2", password="test-pass-123", company=self.b, role=User.Role.ADMIN)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("company_delivery_document", args=[self.delivery.pk])).status_code, 404)


class DriverPanelTests(OperationsTestCase):
    def setUp(self):
        super().setUp()
        self.delivery.driver = self.fleet_driver
        self.delivery.vehicle = self.vehicle
        self.delivery.status = Delivery.Status.DISPATCHING
        self.delivery.save()

    def test_driver_only_sees_own_jobs(self):
        self.client.force_login(self.driver_login)
        response = self.client.get(reverse("driver_jobs"))
        self.assertContains(response, self.delivery.code)
        self.assertNotContains(response, self.delivery_b.code)
        self.assertEqual(self.client.get(reverse("driver_job_detail", args=[self.delivery_b.pk])).status_code, 404)

    def test_driver_is_kept_out_of_the_company_panel(self):
        self.client.force_login(self.driver_login)
        self.assertRedirects(self.client.get(reverse("delivery_list")), reverse("driver_home"))
        self.assertRedirects(self.client.get(reverse("dashboard")), reverse("driver_home"))

    def test_company_user_is_redirected_away_from_driver_panel(self):
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.get(reverse("driver_jobs")), reverse("dashboard"))

    def test_driver_mini_dashboard_shows_the_menu_and_the_next_stop(self):
        self.client.force_login(self.driver_login)
        response = self.client.get(reverse("driver_home"))
        self.assertContains(response, self.delivery.code)
        self.assertContains(response, "sidebar")
        self.assertContains(response, "Entregador")
        self.assertContains(response, "menu-toggle")
        for name in ("driver_jobs", "driver_history", "driver_profile"):
            self.assertContains(response, reverse(name))

    def test_driver_changes_own_availability(self):
        self.client.force_login(self.driver_login)
        self.client.post(reverse("driver_availability"), {"status": Driver.Status.AWAY})
        self.fleet_driver.refresh_from_db()
        self.assertEqual(self.fleet_driver.status, Driver.Status.AWAY)

    def test_accept_then_start_pickup(self):
        self.client.force_login(self.driver_login)
        self.client.post(reverse("driver_accept_job", args=[self.delivery.pk]))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.ACCEPTED)
        self.assertIsNotNone(self.delivery.accepted_at)
        self.client.post(reverse("driver_start_pickup", args=[self.delivery.pk]))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.PICKUP)

    def test_ping_records_position_only_while_running(self):
        self.client.force_login(self.driver_login)
        url = reverse("driver_ping", args=[self.delivery.pk])
        self.assertEqual(self.client.post(url, {"lat": -26.99, "lng": -48.63}, content_type="application/json").status_code, 409)

        self.delivery.status = Delivery.Status.PICKUP
        self.delivery.save()
        response = self.client.post(url, {"lat": -26.99, "lng": -48.63}, content_type="application/json")
        self.assertEqual(response.status_code, 200)
        self.fleet_driver.refresh_from_db()
        self.assertAlmostEqual(self.fleet_driver.last_lat, -26.99)
        self.assertEqual(DriverPing.objects.filter(delivery=self.delivery).count(), 1)

    def test_ping_rejects_invalid_coordinates(self):
        self.delivery.status = Delivery.Status.PICKUP
        self.delivery.save()
        self.client.force_login(self.driver_login)
        response = self.client.post(reverse("driver_ping", args=[self.delivery.pk]), {"lat": 999, "lng": 0}, content_type="application/json")
        self.assertEqual(response.status_code, 400)


@override_settings(MEDIA_ROOT=MEDIA_FOR_TESTS)
class PickupChecklistTests(OperationsTestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(MEDIA_FOR_TESTS, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        super().setUp()
        self.delivery.driver = self.fleet_driver
        self.delivery.vehicle = self.vehicle
        self.delivery.status = Delivery.Status.PICKUP
        self.delivery.save()
        self.url = reverse("driver_checklist", args=[self.delivery.pk])

    def payload(self, photos=12):
        data = {
            "handover_name": "Recepção Clínica", "handover_document": "123.456.789-00",
            "package_count": 1, "seal_number": "LC-8842",
            "identity_checked": "on", "item_matches_request": "on", "packaging_intact": "on",
            "seal_applied": "on", "documents_checked": "on", "photos_are_original": "on",
            "notes": "Item conferido na recepção.", "lat": "-26.9906", "lng": "-48.6349", "accuracy": "8",
        }
        for index, (slot, _) in enumerate(ChecklistPhoto.Slot.choices):
            if index < photos:
                data[f"photo_{slot}"] = fake_photo(f"{slot}.jpg")
        return data

    def test_checklist_requires_all_twelve_photos(self):
        self.client.force_login(self.driver_login)
        response = self.client.post(self.url, self.payload(photos=11))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(PickupChecklist.objects.exists())
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.PICKUP)

    def test_checklist_with_twelve_photos_releases_transport(self):
        self.client.force_login(self.driver_login)
        response = self.client.post(self.url, self.payload())
        self.assertRedirects(response, reverse("driver_job_detail", args=[self.delivery.pk]))
        checklist = PickupChecklist.objects.get(delivery=self.delivery)
        self.assertEqual(checklist.photos.count(), 12)
        self.assertIsNotNone(checklist.submitted_at)
        self.assertEqual(checklist.missing_photo_slots, [])
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.IN_TRANSIT)
        self.assertIsNotNone(self.delivery.picked_up_at)

    def test_delivery_cannot_be_completed_without_checklist(self):
        self.delivery.status = Delivery.Status.IN_TRANSIT
        self.delivery.save()
        self.client.force_login(self.driver_login)
        response = self.client.post(reverse("driver_complete_job", args=[self.delivery.pk]), {"receiver": "João"})
        self.assertRedirects(response, reverse("driver_job_detail", args=[self.delivery.pk]))
        self.delivery.refresh_from_db()
        self.assertEqual(self.delivery.status, Delivery.Status.IN_TRANSIT)

    def test_company_reads_term_and_photos_but_other_company_cannot(self):
        self.client.force_login(self.driver_login)
        self.client.post(self.url, self.payload())
        photo = ChecklistPhoto.objects.first()

        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(reverse("delivery_checklist", args=[self.delivery.pk])).status_code, 200)
        self.assertEqual(self.client.get(reverse("checklist_photo", args=[self.delivery.pk, photo.pk])).status_code, 200)

        outsider = User.objects.create_user("admin-b", password="test-pass-123", company=self.b, role=User.Role.ADMIN)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("delivery_checklist", args=[self.delivery.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("checklist_photo", args=[self.delivery.pk, photo.pk])).status_code, 404)


class TrackingTests(OperationsTestCase):
    def setUp(self):
        super().setUp()
        self.delivery.driver = self.fleet_driver
        self.delivery.status = Delivery.Status.PICKUP
        self.delivery.save()
        self.fleet_driver.register_position(-26.9906, -48.6349)

    def test_company_sees_live_position(self):
        self.client.force_login(self.admin)
        data = self.client.get(reverse("delivery_tracking_data", args=[self.delivery.pk])).json()
        self.assertTrue(data["trackable"])
        self.assertEqual(data["driver"]["name"], "Carlos")
        self.assertAlmostEqual(data["driver"]["lat"], -26.9906)
        self.assertEqual(self.client.get(reverse("delivery_tracking", args=[self.delivery.pk])).status_code, 200)

    def test_position_is_hidden_after_delivery(self):
        self.delivery.status = Delivery.Status.DELIVERED
        self.delivery.save()
        self.client.force_login(self.admin)
        data = self.client.get(reverse("delivery_tracking_data", args=[self.delivery.pk])).json()
        self.assertFalse(data["trackable"])
        self.assertIsNone(data["driver"])

    def test_other_company_cannot_track(self):
        outsider = User.objects.create_user("viewer-b", password="test-pass-123", company=self.b, role=User.Role.VIEWER)
        self.client.force_login(outsider)
        self.assertEqual(self.client.get(reverse("delivery_tracking_data", args=[self.delivery.pk])).status_code, 404)
