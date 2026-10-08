"""
Позиции для заказов, созданных до появления OrderItem.

Цена на момент покупки нигде не сохранялась, поэтому берётся текущая цена варианта —
лучшее доступное приближение. Итог заказа (total_price) не пересчитывается: он был
зафиксирован при оформлении. Позиции без варианта получают первый вариант товара;
позиции, для которых варианта нет вовсе, пропускаются (печатается количество).
"""
from django.db import migrations


def forwards(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    OrderItem = apps.get_model("orders", "OrderItem")
    CartItems = apps.get_model("orders", "CartItems")
    ProductVariant = apps.get_model("products", "ProductVariant")

    created = skipped = 0
    for order in Order.objects.filter(items__isnull=True).iterator():
        for ci in CartItems.objects.filter(cart_id=order.cart_id).select_related("product", "variant"):
            variant = ci.variant or ProductVariant.objects.filter(product_id=ci.product_id).order_by("id").first()
            if variant is None or not ci.quantity:
                skipped += 1
                continue
            OrderItem.objects.create(
                order=order,
                product_id=ci.product_id,
                variant=variant,
                name=variant.variant_name or (ci.product.name if ci.product else "") or "",
                sku=variant.code or "",
                unit_price=variant.price or 0,
                quantity=ci.quantity,
            )
            created += 1
    if created or skipped:
        print(f"\n  [orders.0010] создано позиций: {created}, пропущено без варианта: {skipped}")


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0009_order_items"),
        ("products", "0015_stock_decimal"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
