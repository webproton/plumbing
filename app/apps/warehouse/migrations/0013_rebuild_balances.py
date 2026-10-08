"""
Нормализация журнала и построение остатков.

1. Движения с нулевым количеством (баг парсера: qty=None → 0) удаляются — на остатки они не влияют.
2. Движения с отрицательным количеством переворачиваются в противоположный тип с |qty|.
3. StockBalance строится по журналу для каждой пары (вариант, склад).
4. ProductVariant.stock пересчитывается как сумма по складам (раньше кэш считался с ошибкой
   и учитывал только in/out); reserved обнуляется — до этой версии резервов не было.
"""
from decimal import Decimal

from django.db import migrations
from django.db.models import Q, Sum

INCOMING = ("in", "return_in", "adjustment", "transfer_in")
OUTGOING = ("out", "return_out", "adjustment_out", "transfer_out")
OPPOSITE = {
    "in": "out", "out": "in",
    "return_in": "return_out", "return_out": "return_in",
    "adjustment": "adjustment_out", "adjustment_out": "adjustment",
    "transfer_in": "transfer_out", "transfer_out": "transfer_in",
}


def forwards(apps, schema_editor):
    StockMovement = apps.get_model("warehouse", "StockMovement")
    StockBalance = apps.get_model("warehouse", "StockBalance")
    ProductVariant = apps.get_model("products", "ProductVariant")

    zero = StockMovement.objects.filter(quantity=0)
    zero_count = zero.count()
    zero.delete()

    negatives = list(StockMovement.objects.filter(quantity__lt=0))
    for mv in negatives:
        mv.quantity = -mv.quantity
        mv.movement_type = OPPOSITE.get(mv.movement_type, mv.movement_type)
        mv.save(update_fields=["quantity", "movement_type"])

    rows = (
        StockMovement.objects.values("variant_id", "warehouse_id")
        .annotate(
            inc=Sum("quantity", filter=Q(movement_type__in=INCOMING)),
            out=Sum("quantity", filter=Q(movement_type__in=OUTGOING)),
        )
    )
    totals = {}
    negative_balances = 0
    for row in rows:
        qty = (row["inc"] or Decimal("0")) - (row["out"] or Decimal("0"))
        if qty < 0:
            negative_balances += 1
        StockBalance.objects.update_or_create(
            variant_id=row["variant_id"], warehouse_id=row["warehouse_id"], defaults={"quantity": qty}
        )
        totals[row["variant_id"]] = totals.get(row["variant_id"], Decimal("0")) + qty

    ProductVariant.objects.update(stock=0, reserved=0)
    for variant_id, qty in totals.items():
        ProductVariant.objects.filter(pk=variant_id).update(stock=qty)

    if zero_count or negatives or negative_balances:
        print(
            f"\n  [warehouse.0013] удалено нулевых движений: {zero_count}, "
            f"исправлено отрицательных: {len(negatives)}, "
            f"отрицательных остатков (требуют инвентаризации): {negative_balances}"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0012_stock_decimal"),
        ("products", "0015_stock_decimal"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
