from datetime import timedelta

from django import forms
from django.utils import timezone

from operations.models import Delivery, Driver

from .models import DriverPayout, Invoice, PricingPolicy


class DateInput(forms.DateInput):
    input_type = "date"


class PricingPolicyForm(forms.ModelForm):
    class Meta:
        model = PricingPolicy
        fields = ("base_price", "price_per_extra_stop", "urgent_surcharge", "critical_surcharge", "driver_share_percent")
        help_texts = {
            "price_per_extra_stop": "Cobrado por destino além do primeiro.",
            "driver_share_percent": "Parte do valor da entrega que vira repasse ao entregador.",
        }


class DeliveryPriceForm(forms.ModelForm):
    """Ajuste manual dos valores de uma entrega pelo admin master."""

    class Meta:
        model = Delivery
        fields = ("price", "driver_payout_amount")

    def clean(self):
        cleaned = super().clean()
        price, payout = cleaned.get("price"), cleaned.get("driver_payout_amount")
        if price is not None and payout is not None and payout > price:
            self.add_error("driver_payout_amount", "O repasse não pode ser maior que o valor cobrado da empresa.")
        return cleaned


class InvoiceRequestForm(forms.Form):
    """A empresa escolhe as entregas e a data de vencimento do boleto."""

    due_date = forms.DateField(label="Vencimento do boleto", widget=DateInput())
    deliveries = forms.ModelMultipleChoiceField(
        label="Entregas a faturar", queryset=Delivery.objects.none(), widget=forms.CheckboxSelectMultiple,
    )
    notes = forms.CharField(label="Observações para a fatura", required=False, widget=forms.Textarea(attrs={"rows": 2}))

    def __init__(self, *args, company=None, available=None, suggested_due_date=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.company = company
        self.fields["deliveries"].queryset = available
        self.fields["deliveries"].initial = [item.pk for item in available]
        if suggested_due_date:
            self.fields["due_date"].initial = suggested_due_date
            self.fields["due_date"].help_text = (
                f"Sugerido pelo dia {company.invoice_due_day} que sua empresa escolheu nas configurações."
            )

    def clean_due_date(self):
        due_date = self.cleaned_data["due_date"]
        today = timezone.localdate()
        if due_date < today + timedelta(days=1):
            raise forms.ValidationError("Escolha um vencimento a partir de amanhã.")
        if due_date > today + timedelta(days=180):
            raise forms.ValidationError("O vencimento não pode passar de 180 dias.")
        return due_date


class BankSlipForm(forms.ModelForm):
    """O admin master cola a linha digitável emitida no banco."""

    class Meta:
        model = Invoice
        fields = ("due_date", "bank_slip_line", "bank_slip_url", "notes")
        widgets = {"due_date": DateInput(), "notes": forms.Textarea(attrs={"rows": 2})}

    def clean_bank_slip_line(self):
        line = self.cleaned_data["bank_slip_line"].strip()
        digits = "".join(char for char in line if char.isdigit())
        if line and len(digits) not in (47, 48):
            raise forms.ValidationError("A linha digitável de um boleto tem 47 ou 48 dígitos.")
        return line


class PaymentForm(forms.Form):
    method = forms.CharField(label="Forma de pagamento", max_length=40, initial="Boleto")
    paid_on = forms.DateField(label="Data do pagamento", widget=DateInput(), required=False)

    def clean_paid_on(self):
        return self.cleaned_data.get("paid_on") or timezone.localdate()


class PayoutForm(forms.Form):
    """Fecha um repasse com as entregas concluídas do entregador no período."""

    driver = forms.ModelChoiceField(label="Entregador", queryset=Driver.objects.none())
    reference_start = forms.DateField(label="Período de", widget=DateInput())
    reference_end = forms.DateField(label="Período até", widget=DateInput())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["driver"].queryset = Driver.objects.filter(company__is_platform=True).order_by("name")
        today = timezone.localdate()
        self.fields["reference_start"].initial = today.replace(day=1)
        self.fields["reference_end"].initial = today

    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("reference_start"), cleaned.get("reference_end")
        if start and end and end < start:
            self.add_error("reference_end", "O fim do período não pode ser anterior ao início.")
        return cleaned
