# app/apps/warehouse/inventory/barcode_scanner.py
"""Поиск товара по штрихкоду/артикулу и приёмка сканером в рамках накладной."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Q

from app.apps.products.models import ProductVariant
from app.apps.warehouse import stock
from app.apps.warehouse.models import ProductBarcode


def find_variant_by_code(query):
    """Ищет вариант по доп. штрихкоду, основному штрихкоду или артикулу (без учёта регистра)."""
    code = str(query or "").strip()
    if not code:
        return None
    extra = ProductBarcode.objects.filter(code__iexact=code).select_related("variant").first()
    if extra:
        return extra.variant
    return ProductVariant.objects.filter(Q(barcode__iexact=code) | Q(code__iexact=code)).first()


def find_row_in_document(document, variant):
    """Находит строку распознанной накладной, соответствующую варианту (по SKU, штрихкоду, имени)."""
    items = (document.extracted_data or {}).get("items") or []
    code = (variant.code or "").strip().lower()
    barcode = (variant.barcode or "").strip().lower()
    name = (variant.variant_name or "").strip().lower()
    for row in items:
        if code and str(row.get("sku") or "").strip().lower() == code:
            return row
        if barcode and str(row.get("barcode") or "").strip().lower() == barcode:
            return row
    if name:
        for row in items:
            if str(row.get("name") or "").strip().lower() == name:
                return row
    return None


def scan_barcode(document, barcode, warehouse, user):
    """
    Один пик сканера = приход 1 единицы по документу.
    Если товар не найден — ObjectDoesNotExist (фронт предложит создать карточку).
    Цена прихода берётся из строки накладной, иначе — текущая себестоимость варианта.
    """
    variant = find_variant_by_code(barcode)
    if variant is None:
        raise ObjectDoesNotExist(f"Товар со штрихкодом {barcode} не найден")

    row = find_row_in_document(document, variant)
    price = variant.cost_price
    if row and row.get("price") not in (None, ""):
        try:
            price = Decimal(str(row["price"])).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            pass

    stock.receive(
        variant,
        warehouse,
        1,
        user=user,
        supplier=document.supplier,
        inventory_document=document,
        document_number=document.document_number,
        price_per_unit=price,
        comment=f"Сканер: {barcode}",
    )
    return variant
