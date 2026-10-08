from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0013_rebuild_balances"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="stockmovement",
            constraint=models.CheckConstraint(check=models.Q(quantity__gt=0), name="stockmove_quantity_positive"),
        ),
    ]
