import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    """Cadastro completo da empresa: documento (CNPJ/MEI/CPF), endereço e faturamento."""

    dependencies = [
        ("accounts", "0003_company_address_company_city_company_contact_name_and_more"),
    ]

    operations = [
        migrations.RenameField(model_name="company", old_name="cnpj", new_name="document"),
        migrations.AlterField(
            model_name="company",
            name="document",
            field=models.CharField(max_length=18, unique=True, verbose_name="CNPJ / CPF"),
        ),
        migrations.AddField(
            model_name="company",
            name="document_type",
            field=models.CharField(
                choices=[("cnpj", "CNPJ"), ("mei", "MEI"), ("cpf", "CPF")],
                default="cnpj", max_length=4, verbose_name="tipo de documento",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="legal_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="razão social / nome completo"),
        ),
        migrations.AddField(
            model_name="company",
            name="state_registration",
            field=models.CharField(blank=True, max_length=30, verbose_name="inscrição estadual"),
        ),
        migrations.AddField(
            model_name="company",
            name="zip_code",
            field=models.CharField(blank=True, max_length=10, verbose_name="CEP"),
        ),
        migrations.AddField(
            model_name="company",
            name="district",
            field=models.CharField(blank=True, max_length=90, verbose_name="bairro"),
        ),
        migrations.AddField(
            model_name="company",
            name="state",
            field=models.CharField(blank=True, max_length=2, verbose_name="UF"),
        ),
        migrations.AddField(
            model_name="company",
            name="invoice_due_day",
            field=models.PositiveSmallIntegerField(
                default=10,
                help_text="Usado como sugestão ao faturar entregas em boleto.",
                validators=[
                    django.core.validators.MinValueValidator(1),
                    django.core.validators.MaxValueValidator(28),
                ],
                verbose_name="dia de vencimento preferido",
            ),
        ),
        migrations.AddField(
            model_name="company",
            name="registered_at",
            field=models.DateTimeField(
                blank=True, null=True,
                help_text="Enquanto estiver vazio, a empresa só acessa a própria tela de cadastro.",
                verbose_name="cadastro concluído em",
            ),
        ),
        migrations.AlterField(
            model_name="company",
            name="name",
            field=models.CharField(max_length=160, verbose_name="nome fantasia"),
        ),
        migrations.AlterField(
            model_name="company",
            name="address",
            field=models.CharField(blank=True, max_length=255, verbose_name="logradouro e número"),
        ),
    ]
