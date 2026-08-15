from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="notification",
            name="audience",
            field=models.CharField(
                choices=[("platform", "Central"), ("company", "Empresa")],
                default="platform",
                max_length=10,
                verbose_name="destinatário",
            ),
        ),
        migrations.AlterField(
            model_name="notification",
            name="kind",
            field=models.CharField(
                choices=[
                    ("request", "Nova solicitação de entrega"),
                    ("invoice", "Pedido de faturamento"),
                    ("company", "Cadastro de empresa concluído"),
                    ("update", "Atualização da entrega"),
                ],
                max_length=10,
                verbose_name="tipo",
            ),
        ),
        migrations.AddIndex(
            model_name="notification",
            index=models.Index(fields=["audience", "read_at", "-created_at"], name="aviso_por_destinatario"),
        ),
    ]
