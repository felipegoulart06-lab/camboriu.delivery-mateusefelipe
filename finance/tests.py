from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company, User
from core.models import Notification
from operations.models import Delivery, Driver

from .models import DriverPayout, Invoice, PricingPolicy
from .reports import company_metrics, default_due_date, driver_metrics, headline


class FinanceTestCase(TestCase):
    def setUp(self):
        self.platform = Company.objects.create(
            name="Camboriú Delivery", slug="plataforma", document="11.111.111/0001-11",
            is_platform=True, registered_at=timezone.now(),
        )
        self.company = Company.objects.create(
            name="Empresa Alfa", legal_name="Alfa Comércio LTDA", slug="alfa",
            document="22.333.444/0001-55", document_type=Company.DocumentType.CNPJ,
            city="Balneário Camboriú", state="SC", invoice_due_day=10, registered_at=timezone.now(),
        )
        self.cash_company = Company.objects.create(
            name="Ateliê CPF", slug="cpf", document="123.456.789-09",
            document_type=Company.DocumentType.CPF, registered_at=timezone.now(),
        )
        self.master = User.objects.create_user("master", password="test-pass-123", company=self.platform, role=User.Role.MASTER)
        self.dispatcher = User.objects.create_user("central", password="test-pass-123", company=self.platform, role=User.Role.DISPATCHER)
        self.owner = User.objects.create_user("alfa", password="test-pass-123", company=self.company, role=User.Role.OWNER)
        self.cash_owner = User.objects.create_user("cpf-user", password="test-pass-123", company=self.cash_company, role=User.Role.OWNER)
        driver_login = User.objects.create_user("carlos", password="test-pass-123", company=self.platform, role=User.Role.DRIVER)
        self.driver = Driver.objects.create(
            company=self.platform, user=driver_login, name="Carlos Mendes", cpf="1", cnh="1",
            cnh_category="AB", phone="(47) 99911-2200", contract_type=Driver.Contract.EMPLOYEE,
        )
        self.policy = PricingPolicy.current()

    def delivered(self, company=None, price="30.00", payout="21.00"):
        delivery = Delivery.objects.create(
            company=company or self.company, requester="Cliente", item_type=Delivery.ItemType.DOCUMENT,
            description="Teste", pickup_address="A", pickup_contact="A",
            delivery_address="B", delivery_contact="B", driver=self.driver, status=Delivery.Status.DELIVERED,
        )
        Delivery.objects.filter(pk=delivery.pk).update(price=Decimal(price), driver_payout_amount=Decimal(payout))
        delivery.refresh_from_db()
        return delivery


class PricingTests(FinanceTestCase):
    def test_quote_adds_extra_stops_and_priority(self):
        delivery = self.delivered(price="0", payout="0")
        delivery.priority = Delivery.Priority.URGENT
        self.assertEqual(
            self.policy.quote(delivery),
            self.policy.base_price + self.policy.urgent_surcharge,
        )

    def test_only_master_edits_the_price_table(self):
        self.client.force_login(self.dispatcher)
        self.assertRedirects(self.client.get(reverse("finance_pricing")), reverse("platform_home"))
        self.client.force_login(self.master)
        response = self.client.post(reverse("finance_pricing"), {
            "base_price": "30.00", "price_per_extra_stop": "12.00", "urgent_surcharge": "9.00",
            "critical_surcharge": "20.00", "driver_share_percent": "65.00",
        })
        self.assertRedirects(response, reverse("finance_dashboard"))
        self.assertEqual(PricingPolicy.current().base_price, Decimal("30.00"))

    def test_payout_cannot_exceed_the_price(self):
        delivery = self.delivered()
        self.client.force_login(self.master)
        response = self.client.post(reverse("delivery_price", args=[delivery.pk]), {"price": "10.00", "driver_payout_amount": "50.00"})
        self.assertContains(response, "não pode ser maior")


class InvoiceTests(FinanceTestCase):
    def test_company_with_cnpj_invoices_choosing_the_due_date(self):
        first, second = self.delivered(), self.delivered(price="45.00", payout="31.50")
        due = timezone.localdate() + timedelta(days=20)
        self.client.force_login(self.owner)
        response = self.client.post(reverse("company_invoice_request"), {
            "due_date": due.isoformat(), "deliveries": [first.pk, second.pk], "notes": "Fechamento quinzenal",
        })
        invoice = Invoice.objects.get(company=self.company)
        self.assertRedirects(response, reverse("company_invoice_detail", args=[invoice.pk]))
        self.assertEqual(invoice.total, Decimal("75.00"))
        self.assertEqual(invoice.due_date, due)
        self.assertEqual(invoice.kind, Invoice.Kind.BANK_SLIP)
        self.assertEqual(invoice.deliveries.count(), 2)
        self.assertTrue(Notification.objects.filter(kind=Notification.Kind.INVOICE_REQUEST, company=self.company).exists())

    def test_due_date_must_be_in_the_future(self):
        self.delivered()
        self.client.force_login(self.owner)
        response = self.client.post(reverse("company_invoice_request"), {
            "due_date": timezone.localdate().isoformat(), "deliveries": [],
        })
        self.assertContains(response, "a partir de amanhã")
        self.assertFalse(Invoice.objects.exists())

    def test_company_with_cpf_cannot_invoice_in_bank_slip(self):
        self.delivered(company=self.cash_company)
        self.client.force_login(self.cash_owner)
        self.assertRedirects(self.client.get(reverse("company_invoice_request")), reverse("company_billing"))
        with self.assertRaises(Exception):
            Invoice.create_for(self.cash_company, [], timezone.localdate())

    def test_suggested_due_date_follows_the_company_preference(self):
        self.assertEqual(default_due_date(self.company).day, 10)

    def test_master_registers_the_bank_slip_and_the_company_sees_it(self):
        delivery = self.delivered()
        invoice = Invoice.create_for(self.company, [delivery], timezone.localdate() + timedelta(days=10))
        line = "34191790010104351004791020150008912340000012345"
        self.client.force_login(self.master)
        self.client.post(reverse("invoice_bank_slip", args=[invoice.pk]), {
            "due_date": invoice.due_date.isoformat(), "bank_slip_line": line, "bank_slip_url": "", "notes": "",
        })
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)

        self.client.force_login(self.owner)
        response = self.client.get(reverse("company_invoice_detail", args=[invoice.pk]))
        self.assertContains(response, line)

    def test_bank_slip_line_length_is_validated(self):
        delivery = self.delivered()
        invoice = Invoice.create_for(self.company, [delivery], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.master)
        response = self.client.post(reverse("invoice_bank_slip", args=[invoice.pk]), {
            "due_date": invoice.due_date.isoformat(), "bank_slip_line": "123", "bank_slip_url": "", "notes": "",
        })
        self.assertContains(response, "47 ou 48")

    def test_paying_moves_the_value_to_received(self):
        invoice = Invoice.create_for(self.company, [self.delivered()], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.master)
        self.client.post(reverse("invoice_pay", args=[invoice.pk]), {"method": "Boleto", "paid_on": timezone.localdate().isoformat()})
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertEqual(headline()["received_month"], invoice.total)

    def test_canceling_returns_the_deliveries_to_the_queue(self):
        delivery = self.delivered()
        invoice = Invoice.create_for(self.company, [delivery], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.master)
        self.client.post(reverse("invoice_cancel", args=[invoice.pk]), {"confirm": "1"})
        delivery.refresh_from_db()
        self.assertIsNone(delivery.invoice_id)
        self.assertTrue(delivery.is_billable)

    def test_canceling_without_confirmation_keeps_the_invoice(self):
        delivery = self.delivered()
        invoice = Invoice.create_for(self.company, [delivery], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.master)
        self.client.post(reverse("invoice_cancel", args=[invoice.pk]))
        invoice.refresh_from_db()
        delivery.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.OPEN)
        self.assertEqual(delivery.invoice_id, invoice.pk)

    def test_invoice_pdf_is_generated(self):
        invoice = Invoice.create_for(self.company, [self.delivered()], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.master)
        response = self.client.get(reverse("invoice_document", args=[invoice.pk]))
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_company_only_reads_its_own_invoice(self):
        invoice = Invoice.create_for(self.company, [self.delivered()], timezone.localdate() + timedelta(days=5))
        self.client.force_login(self.cash_owner)
        self.assertEqual(self.client.get(reverse("company_invoice_detail", args=[invoice.pk])).status_code, 404)


class PayoutTests(FinanceTestCase):
    def test_master_closes_and_pays_a_payout(self):
        self.delivered(), self.delivered(price="45.00", payout="31.50")
        today = timezone.localdate()
        self.client.force_login(self.master)
        self.client.post(reverse("payout_create"), {
            "driver": self.driver.pk, "reference_start": today.replace(day=1).isoformat(), "reference_end": today.isoformat(),
        })
        payout = DriverPayout.objects.get(driver=self.driver)
        self.assertEqual(payout.total, Decimal("52.50"))
        self.assertEqual(payout.rides, 2)

        self.client.post(reverse("payout_pay", args=[payout.pk]), {"method": "Pix", "paid_on": today.isoformat()})
        payout.refresh_from_db()
        self.assertEqual(payout.status, DriverPayout.Status.PAID)
        self.assertEqual(headline()["payout_paid_total"], Decimal("52.50"))

    def test_driver_metrics_split_transferred_and_pending(self):
        self.delivered()
        pending = self.delivered(price="45.00", payout="31.50")
        payout = DriverPayout.create_for(
            self.driver, [self.driver.delivery_set.exclude(pk=pending.pk).first()],
            timezone.localdate(), timezone.localdate(),
        )
        payout.mark_paid("Pix")
        row = next(item for item in driver_metrics() if item["driver"] == self.driver)
        self.assertEqual(row["rides"], 2)
        self.assertEqual(row["transferred"], Decimal("21.00"))
        self.assertEqual(row["pending"], Decimal("31.50"))
        self.assertEqual(row["earned"], Decimal("52.50"))

    def test_company_metrics_do_not_multiply_invoices_by_deliveries(self):
        first, second = self.delivered(), self.delivered(price="45.00", payout="31.50")
        invoice = Invoice.create_for(self.company, [first, second], timezone.localdate() + timedelta(days=5))
        row = next(item for item in company_metrics() if item["company"] == self.company)
        self.assertEqual(row["rides"], 2)
        self.assertEqual(row["billed_total"], Decimal("75.00"))
        self.assertEqual(row["receivable"], invoice.total)
        self.assertEqual(row["not_billed"], Decimal("0.00"))

    def test_dispatcher_reads_the_dashboard_but_does_not_pay(self):
        self.client.force_login(self.dispatcher)
        self.assertEqual(self.client.get(reverse("finance_dashboard")).status_code, 200)
        self.assertRedirects(self.client.get(reverse("payout_create")), reverse("platform_home"))

    def test_company_user_cannot_open_the_accounting_panel(self):
        self.client.force_login(self.owner)
        self.assertRedirects(self.client.get(reverse("finance_dashboard")), reverse("dashboard"))

    def test_driver_sees_what_was_transferred(self):
        self.delivered()
        payout = DriverPayout.create_for(self.driver, self.driver.delivery_set.all(), timezone.localdate(), timezone.localdate())
        payout.mark_paid("Pix")
        self.client.force_login(self.driver.user)
        response = self.client.get(reverse("driver_history"))
        self.assertContains(response, "21,00")

    def test_undo_payout_without_confirmation_keeps_the_lot(self):
        self.delivered()
        payout = DriverPayout.create_for(self.driver, self.driver.delivery_set.all(), timezone.localdate(), timezone.localdate())
        self.client.force_login(self.master)
        self.client.post(reverse("payout_reopen", args=[payout.pk]))
        self.assertTrue(DriverPayout.objects.filter(pk=payout.pk).exists())

    def test_undo_payout_with_confirmation_returns_deliveries_to_the_queue(self):
        delivery = self.delivered()
        payout = DriverPayout.create_for(self.driver, [delivery], timezone.localdate(), timezone.localdate())
        self.client.force_login(self.master)
        self.client.post(reverse("payout_reopen", args=[payout.pk]), {"confirm": "1"})
        self.assertFalse(DriverPayout.objects.filter(pk=payout.pk).exists())
        delivery.refresh_from_db()
        self.assertIsNone(delivery.payout_id)
