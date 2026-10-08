# app/apps/warehouse/services.py
"""
Проведение накладных поставщиков: парсинг → сопоставление строк с вариантами → приход на склад.
Все изменения остатков — через app.apps.warehouse.stock.
"""
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from rapidfuzz import fuzz

from parsers.core.loader import load_rows
from parsers.registry import parse as run_invoice_parser

from app.apps.products.models import Product, ProductVariant
from app.apps.warehouse import stock
from app.apps.warehouse.models import InventoryDocument, ProductBarcode, VariantMatchMemory, Warehouse

logger = logging.getLogger(__name__)

RETAIL_MARKUP = Decimal("1.40")


def build_variant_cache():
    """ Кэширует базу товаров в ОЗУ для ускорения поиска в 50+ раз """
    variants = ProductVariant.objects.all().values("id", "variant_name", "code", "barcode")

    cache = {
        "by_id": {},
        "code": {},
        "barcode": {},
    }

    for v in variants:
        vid = v["id"]
        cache["by_id"][vid] = v

        code = v.get("code")
        if code:
            cache["code"][str(code).strip().lower()] = vid

        barcode = v.get("barcode")
        if barcode:
            cache["barcode"][str(barcode).strip().lower()] = vid

    return cache


def match_variant_learning(row, cache, supplier=None):
    """ Умное сопоставление строки из накладной с товаром из кэша базы """
    row_sku = str(row.get("sku") or "").strip().lower()
    row_barcode = str(row.get("barcode") or "").strip().lower()
    name = str(row.get("name") or "").strip()

    # 1. MEMORY (1С-логика)
    memory_qs = VariantMatchMemory.objects.filter(supplier=supplier)

    if row_sku:
        memory = memory_qs.filter(raw_code=row_sku).select_related("variant").first()
        if memory:
            memory.hit_count = (memory.hit_count or 0) + 1
            memory.save(update_fields=["hit_count"])
            return memory.variant, 1.0

    if name:
        memory = memory_qs.filter(raw_name=name).select_related("variant").first()
        if memory:
            memory.hit_count = (memory.hit_count or 0) + 1
            memory.save(update_fields=["hit_count"])
            return memory.variant, 1.0

    # 2. BARCODE MATCH
    if row_barcode:
        variant_id = cache["barcode"].get(row_barcode)
        if variant_id:
            return ProductVariant.objects.get(id=variant_id), 1.0

        alt_barcode = ProductBarcode.objects.filter(code=row_barcode).select_related("variant").first()
        if alt_barcode:
            return alt_barcode.variant, 1.0

    # 3. CODE (SKU) MATCH
    if row_sku:
        variant_id = cache["code"].get(row_sku)
        if variant_id:
            return ProductVariant.objects.get(id=variant_id), 0.95

    # 4. FUZZY NAME MATCH
    best_variant_id = None
    best_score = 0

    for variant_id, v in cache["by_id"].items():
        vname = v.get("variant_name") or ""
        if not vname or not name:
            continue

        score = fuzz.token_sort_ratio(name, vname)

        if score > best_score:
            best_score = score
            best_variant_id = variant_id

    if best_variant_id and best_score > 80:
        return ProductVariant.objects.get(id=best_variant_id), best_score / 100

    return None, 0.0


def learn_variant_match(row, variant, supplier=None):
    """ 1С-логика: запоминаем выбор сопоставления товара """
    code = str(row.get("sku") or "").strip()
    name = str(row.get("name") or "").strip()

    if not name:
        return

    obj, created = VariantMatchMemory.objects.get_or_create(
        supplier=supplier,
        raw_code=code,
        raw_name=name,
        defaults={
            "variant": variant,
            "confidence": 1.0
        }
    )

    if not created:
        obj.hit_count += 1
        obj.variant = variant
        obj.save()


@transaction.atomic
def process_inventory_document(document: InventoryDocument, warehouse: Warehouse, created_by):
    """
    Проводит накладную: парсинг файла (или ранее распознанные данные) → сопоставление строк →
    приход каждой строки на склад. Идемпотентно: документ блокируется, повторное проведение запрещено.
    Возвращает отчёт {"received": int, "skipped": [{"row": n, "reason": str}]}.
    """
    document = InventoryDocument.objects.select_for_update().get(pk=document.pk)
    if document.processed:
        raise stock.StockError("Документ уже проведён")
    if warehouse.seller_id != document.seller_id:
        raise stock.StockError("Склад не принадлежит продавцу документа")

    if document.extracted_data and "items" in document.extracted_data:
        parsed_data = document.extracted_data
    else:
        rows = load_rows(document.file.path)
        parsed_data = run_invoice_parser(rows)
        document.extracted_data = parsed_data
        extracted_num = parsed_data.get("meta", {}).get("number")
        if extracted_num and not document.document_number:
            document.document_number = extracted_num

    supplier = document.supplier
    variant_cache = build_variant_cache()
    report = {"received": 0, "skipped": []}

    for position, row in enumerate(parsed_data.get("items", []), start=1):
        name = row.get("name")
        if not name:
            report["skipped"].append({"row": position, "reason": "нет наименования"})
            continue
        try:
            qty = stock.to_quantity(row.get("qty"))
        except stock.StockError:
            report["skipped"].append({"row": position, "name": name, "reason": f"некорректное количество: {row.get('qty')!r}"})
            continue
        try:
            invoice_price = Decimal(str(row.get("price") or 0)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        except (InvalidOperation, ValueError):
            report["skipped"].append({"row": position, "name": name, "reason": f"некорректная цена: {row.get('price')!r}"})
            continue

        variant_code = row.get("sku")
        barcode = row.get("barcode")
        variant, confidence = match_variant_learning(row, variant_cache, supplier=supplier)

        if not variant:
            # Новый товар скрыт из каталога, пока продавец не проверит карточку.
            product = Product.objects.create(name=name, seller=document.seller)
            variant = ProductVariant.objects.create(
                product=product,
                variant_name=name,
                code=variant_code or None,
                cost_price=invoice_price,
                price=(invoice_price * RETAIL_MARKUP).quantize(Decimal("0.01")),
                barcode=barcode or None,
                available=False,
            )
            variant_cache["by_id"][variant.id] = {"id": variant.id, "variant_name": name,
                                                  "code": variant_code, "barcode": barcode}
            if variant_code:
                variant_cache["code"][str(variant_code).strip().lower()] = variant.id
            if barcode:
                variant_cache["barcode"][str(barcode).strip().lower()] = variant.id
            confidence = 1.0
        elif variant.cost_price != invoice_price:
            # Розничную цену не трогаем — это настройка продавца.
            ProductVariant.objects.filter(pk=variant.pk).update(cost_price=invoice_price)

        learn_variant_match(row, variant, supplier=supplier)
        if barcode:
            ProductBarcode.objects.get_or_create(code=str(barcode).strip(), defaults={"variant": variant})

        stock.receive(
            variant, warehouse, qty,
            user=created_by,
            supplier=supplier,
            inventory_document=document,
            document_number=document.document_number,
            price_per_unit=invoice_price,
            comment=f"Импорт ({parsed_data.get('detected_supplier', 'unknown')}), строка {position}, "
                    f"точность сопоставления {int(confidence * 100)}%",
        )
        report["received"] += 1

    parsed_data["processing_report"] = report
    document.extracted_data = parsed_data
    document.processed = True
    document.save()
    return report
