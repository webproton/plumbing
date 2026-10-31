from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("imports", "0004_supplier_item_cost_currency"),
    ]

    operations = [
        migrations.AddField(
            model_name="importsource",
            name="currency_rates",
            field=models.JSONField(
                blank=True, default=dict, help_text='Курс поставщика к гривне: {"USD": 46.55, "EUR": 50.1}'
            ),
        ),
    ]
