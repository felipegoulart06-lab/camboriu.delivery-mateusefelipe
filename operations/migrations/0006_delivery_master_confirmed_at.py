from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("operations", "0005_delivery_delivery_status_recentes_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="delivery",
            name="master_confirmed_at",
            field=models.DateTimeField("confirmada pela central", blank=True, null=True),
        ),
    ]
