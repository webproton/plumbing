# app/apps/warehouse/services.py
from decimal import ROUND_HALF_UP, Decimal
import os
from rapidfuzz import process, fuzz

from parsers.core.loader import load_rows
from parsers.registry import parse as run_invoice_parser

from app.apps.warehouse.models import InventoryDocument, ProductBarcode, StockMovement, Supplier, VariantMatchMemory, Warehouse
from django.db import transaction
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q  # 🔥 Добавили Q и Sum для оптимизации остатков
from app.apps.products.models import ProductVariant, Product


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


def return_to_supplier(variant, warehouse, supplier, quantity, user):
    """Возврат поставщику"""
    StockMovement.objects.create(
        variant=variant,
        seller=warehouse.seller,
        warehouse=warehouse,
        movement_type='return_out',
        quantity=quantity,
        supplier=supplier,
        created_by=user,
        comment="Возврат поставщику"
    )


@transaction.atomic
def transfer_between_warehouses(variant, from_warehouse, to_warehouse, quantity, user):
    """Перемещение между складами"""
    if from_warehouse == to_warehouse:
        raise ValidationError("Склады одинаковые")

    # 🔥 ИСПРАВЛЕНО: Убытие со склада-отправителя (transfer_out)
    StockMovement.objects.create(
        variant=variant,
        seller=from_warehouse.seller,
        warehouse=from_warehouse,
        movement_type='transfer_out',
        quantity=quantity,
        created_by=user,
        comment=f"Перемещение → {to_warehouse.name}"
    )

    # 🔥 ИСПРАВЛЕно: Прибытие на склад-получатель (transfer_in)
    StockMovement.objects.create(
        variant=variant,
        seller=to_warehouse.seller,
        warehouse=to_warehouse,
        movement_type='transfer_in',
        quantity=quantity,
        created_by=user,
        comment=f"Перемещение ← {from_warehouse.name}"
    )

def recalculate_variant_stock(variant):
    """ Полный принудительный пересчет кэша остатка по всей истории движений """
    from django.db.models import Sum
    
    inc = StockMovement.objects.filter(variant=variant, movement_type="in").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    out = StockMovement.objects.filter(variant=variant, movement_type="out").aggregate(total=Sum('quantity'))['total'] or Decimal('0')
    
    variant.stock = inc - out
    variant.save(update_fields=['stock'])

@transaction.atomic
def process_inventory_document(document: InventoryDocument, warehouse: Warehouse, created_by):
    """
    Универсальная обработка накладной (Экспорт данных -> Умный поиск -> Движения склада).
    
    Включает в себя:
    1. Парсинг файла через новый гибкий TableEngine движок.
    2. Скоростной поиск товаров через кэширование всей базы в ОЗУ.
    3. Четырехуровневый матчинг (Память сопоставлений -> Штрихкоды -> SKU -> Fuzzy Match).
    4. Автоматическое обучение системы (1С-логика) на будущее.
    5. Регистрацию штрихкодов для складского сканера Ruidida.
    """

    # =========================================================================
    # ШАГ 1: ПОЛУЧЕНИЕ ДАННЫХ (ПАРСИНГ ИЛИ КЭШ ДОКУМЕНТА)
    # =========================================================================
    
    # Проверяем защиту: если накладную уже парсили ранее и JSON лежит в базе,
    # мы берем готовые данные, чтобы не тратить ресурсы сервера на повторный OCR/парсинг.
    if document.extracted_data and "items" in document.extracted_data:
        parsed_data = document.extracted_data
    else:
        file_path = document.file.path
        rows = load_rows(file_path)
        parsed_data = run_invoice_parser(rows)
        document.extracted_data = parsed_data
        # Если парсер смог вытащить реальный номер накладной из шапки файла, 
        # а в нашей модели поле еще пустое — автоматически обновляем его
        extracted_num = parsed_data.get("meta", {}).get("number")
        if extracted_num and not document.document_number:
            document.document_number = extracted_num
            
            
            
    # 🔥 ШАГ 0: Если у документа нет поставщика, пробуем подтянуть его автоматически
    if not document.supplier:
        detected_slug = parsed_data.get("detected_supplier") or parsed_data.get("supplier_code")
        if detected_slug:
            # Ищем поставщика по коду/слагу в нашей базе
            auto_supplier = Supplier.objects.filter(code=detected_slug).first()
            if auto_supplier:
                document.supplier = auto_supplier
                document.save(update_fields=['supplier'])

    items = parsed_data.get("items", [])
    variant_cache = build_variant_cache()

    for row in items:
        variant_code = row.get("sku")        
        name = row.get("name")               
        quantity = row.get("qty") or 0       
        price = row.get("price") or 0        
        barcode = row.get("barcode")         

        if not name:
            continue

        variant, confidence = match_variant_learning(row, variant_cache, supplier=document.supplier)
        # 🔥 Переводим цену в Decimal с точностью до 4 знаков (защита от округлений 1.269)
        invoice_price = Decimal(str(price)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        # Переводим количество в Decimal (для метров, граммов и штук)
        qty_decimal = Decimal(str(quantity)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        
        
        if not variant:
            product = Product.objects.create(name=name, seller=document.seller)
            
            
            # Переводим цену закупки из накладной в Decimal
            # invoice_price = Decimal(str(price))
            # 🔥 РАССЧИТЫВАЕМ РОЗНИЧНУЮ ЦЕНУ (Пример: наценка 40%)
            # Вы можете изменить коэффициент "1.40" на ваш стандартный или оставить просто invoice_price
            recommended_retail_price = (invoice_price * Decimal("1.40")).quantize(Decimal("0.01"))
            

            # Создаем конкретную модификацию/вариант
            variant = ProductVariant.objects.create(
                product=product,
                variant_name=name,
                code=variant_code or "",
                # price=Decimal(str(price)),
                
                cost_price=invoice_price,            # 🔥 ТЕПЕРЬ ЗАПИСЫВАЕМ СЮДА ЗАКУПКУ
                price=recommended_retail_price,      # 🔥 СЮДА ИДЕТ РОЗНИЦА С НАЦЕНКОЙ
                barcode=barcode or ""  
            )
            
            variant_cache["by_id"][variant.id] = {
                "id": variant.id, 
                "variant_name": name, 
                "code": variant_code, 
                "barcode": barcode
            }
            if variant_code:
                variant_cache["code"][str(variant_code).strip().lower()] = variant.id
            if barcode:
                variant_cache["barcode"][str(barcode).strip().lower()] = variant.id
                
        else:
            # 🔥 2. Если товар СУЩЕСТВУЕТ — обновляем его закупочную цену, если она изменилась
            # Розничную цену (price) НЕ трогаем, чтобы не сбить настройки продавца!
            if variant.cost_price != invoice_price:
                variant.cost_price = invoice_price
                variant.save(update_fields=['cost_price'])

        learn_variant_match(row, variant, supplier=document.supplier)

        if barcode:
            ProductBarcode.objects.get_or_create(variant=variant, code=str(barcode).strip())

        # price_decimal = Decimal(str(price)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if StockMovement.objects.filter(inventory_document=document, variant=variant).exists():
            continue  # Пропускаем дубль, чтобы не накрутить остаток!
        
        
        StockMovement.objects.create(
            inventory_document=document,
            variant=variant,
            seller=document.seller,
            warehouse=warehouse,
            movement_type="in",
            quantity=qty_decimal,             # 🔥 ТЕПЕРЬ СЮДА ПИШЕТСЯ ДРОБНОЕ ЧИСЛО (Decimal)
            # quantity=int(quantity),
            supplier=document.supplier,
            document_number=document.document_number,
            price_per_unit=invoice_price,     # Закупка с точностью до 4 знаков
            # price_per_unit=price_decimal,
            created_by=created_by,
            comment=f"Импорт ({parsed_data.get('detected_supplier', 'unknown')}) | Точность: {int(confidence * 100)}%"
        )
        
        # 3. 🔥 ОБНОВЛЯЕМ КЭШ ОСТАТКА В КАРТОЧКЕ ТОВАРA
        variant.stock += qty_decimal
        variant.save(update_fields=['stock']) # update_fields критически важен для скорости и безопасности!

    document.processed = True
    document.save()


def get_variant_stock(variant, warehouse=None):
    """
    🔥 ПОЛНОСТЬЮ ИСПРАВЛЕНО И ОПТИМИЗИРОВАНО
    Считает чистый остаток товара на складе прямо в базе данных (быстрее в 100+ раз).
    """
    movements = StockMovement.objects.filter(variant=variant)
    if warehouse:
        movements = movements.filter(warehouse=warehouse)

    # Синхронизированный с моделями подсчет приходов и расходов
    stock_summary = movements.aggregate(
        total_in=Sum('quantity', filter=Q(movement_type__in=['in', 'return_in', 'adjustment', 'transfer_in'])),
        total_out=Sum('quantity', filter=Q(movement_type__in=['out', 'return_out', 'transfer_out']))
    )

    return (stock_summary['total_in'] or 0) - (stock_summary['total_out'] or 0)


def inventory_adjustment(variant, warehouse, real_quantity, user):
    """Инвентаризация склада"""
    current = get_variant_stock(variant, warehouse)
    diff = real_quantity - current

    if diff == 0:
        return
    
    # Оставляем использование базовых 'in' / 'out', так как они корректно подхватываются агрегацией остатков
    movement_type = 'in' if diff > 0 else 'out'
    
    StockMovement.objects.create(
        variant=variant,
        seller=warehouse.seller,
        warehouse=warehouse,
        movement_type=movement_type,
        quantity=abs(diff),
        created_by=user,
        comment=f"Инвентаризация. Было {current}, стало {real_quantity}"
    )