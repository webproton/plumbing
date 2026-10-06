

# app/apps/warehouse/inventory/barcode_scanner.py
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ObjectDoesNotExist
from app.apps.products.models import ProductVariant, Product
from app.apps.warehouse.models import StockMovement, ProductBarcode


def scan_barcode(document, barcode, warehouse, user):
    barcode_str = str(barcode).strip()
    
    with transaction.atomic():
        # =====================
        # 1. Поиск по barcode
        # =====================
        variant = ProductVariant.objects.filter(barcode=barcode_str).first()

        # Поиск в альтернативной таблице баркодов
        if not variant:
            barcode_obj = ProductBarcode.objects.filter(code=barcode_str).first()
            if barcode_obj:
                variant = barcode_obj.variant

        # Если до сих пор не нашли, проверим поле code (вдруг сканер выдал SKU)
        if not variant:
            variant = ProductVariant.objects.filter(code=barcode_str).first()

        # =====================
        # 2. Если товара вообще нет в базе — создаем
        # =====================
        if not variant:
            # ИСПРАВЛЕНО: seller должен быть document.seller, а не supplier
            product = Product.objects.create(
                name=f"NEW {barcode_str}",
                seller=document.seller  
            )

            variant = ProductVariant.objects.create(
                product=product,
                variant_name=f"NEW {barcode_str}",
                code=barcode_str, # записываем код и в SKU
                barcode=barcode_str,
                price=Decimal("0.00")
            )

        # =====================
        # 3. Ищем строку в распознанной накладной
        # =====================
        row = find_row_in_document(document, variant)
        
        # Безопасно вытаскиваем цену из накладной поставщика
        if row and row.get("price"):
            try:
                price = Decimal(str(row["price"])).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            except (ValueError, TypeError):
                price = variant.price or Decimal("0.00")
        else:
            price = variant.price or Decimal("0.00")

        # =====================
        # 4. Создаем или обновляем движение по складу
        # =====================
        movement = StockMovement.objects.filter(
            inventory_document=document,
            variant=variant,
            warehouse=warehouse,
            movement_type="in"
        ).first()

        if movement:
            # ИСПРАВЛЕНО: каждый повторный пик сканера добавляет строго 1 штуку
            movement.quantity += 1
            movement.save()
        else:
            # Первый пик этого товара — создаем запись с количеством 1
            StockMovement.objects.create(
                inventory_document=document,
                variant=variant,
                seller=document.seller,
                warehouse=warehouse,
                movement_type="in",
                quantity=1, 
                supplier=document.supplier,
                document_number=document.document_number,
                price_per_unit=price, # ИСПРАВЛЕНО: используем безопасную переменную price
                created_by=user,
                comment=f"Scan {barcode_str}"
            )

        return variant


def find_row_in_document(document, variant):
    if not document.extracted_data:
        return None

    # Защита от пустых значений, чтобы не сопоставить null == null
    variant_code = str(variant.code).lower() if variant.code else None
    variant_barcode = str(variant.barcode).lower() if variant.barcode else None
    variant_name = variant.variant_name.lower() if variant.variant_name else None

    for table in document.extracted_data.get("tables", []):
        for row in table.get("rows", []):
            
            row_code = str(row.get("code", "")).lower() or None
            row_barcode = str(row.get("barcode", "")).lower() or None
            row_name = row.get("name", "").lower()

            # Сверяем по SKU
            if variant_code and row_code == variant_code:
                return row

            # Сверяем по штрихкоду
            if variant_barcode and row_barcode == variant_barcode:
                return row

            # Сверяем по вхождению имени
            if variant_name and variant_name in row_name:
                return row

    return None
















# from decimal import Decimal

# from app.apps.products.models import ProductVariant, Product
# from app.apps.warehouse.models import StockMovement,ProductBarcode
# from django.db import transaction


# def scan_barcode(document, barcode, warehouse, user):

#     with transaction.atomic():

#         # =====================
#         # поиск по barcode
#         # =====================

#         variant = ProductVariant.objects.filter(
#             barcode=barcode
#         ).first()

#         # поиск в таблице barcode
#         if not variant:
#             barcode_obj = ProductBarcode.objects.filter(
#                 code=barcode
#             ).first()

#             if barcode_obj:
#                 variant = barcode_obj.variant

#         # =====================
#         # если товара нет — создаем
#         # =====================

#         if not variant:

#             product = Product.objects.create(
#                 name=f"NEW {barcode}",
#                 seller=document.supplier
#             )

#             variant = ProductVariant.objects.create(
#                 product=product,
#                 variant_name=f"NEW {barcode}",
#                 barcode=barcode
#             )

#         # =====================
#         # ищем в накладной
#         # =====================

#         row = find_row_in_document(document, variant)

#         if row:
#             quantity = row.get("quantity", 1)
#             price = row.get("price", 0)
#         else:
#             quantity = 1
#             price = 0

#         # =====================
#         # создаем движение
#         # =====================

#         movement = StockMovement.objects.filter(
#             inventory_document=document,
#             variant=variant,
#             warehouse=warehouse,
#             movement_type="in"
#         ).first()

#         if movement:
#             movement.quantity += quantity
#             movement.save()
#         else:
#             StockMovement.objects.create(
#                 inventory_document=document,
#                 variant=variant,
#                 seller=variant.product.seller,
#                 warehouse=warehouse,
#                 movement_type="in",
#                 quantity=quantity,
#                 supplier=document.supplier,
#                 document_number=document.document_number,
#                 price_per_unit=Decimal(str(row["price"])),
#                 created_by=user,
#                 comment=f"Scan {barcode}"
#             )

#         return variant


# def find_row_in_document(document, variant):

#     if not document.extracted_data:
#         return None

#     for table in document.extracted_data.get("tables", []):
#         for row in table.get("rows", []):

#             if row.get("code") == variant.code:
#                 return row

#             if row.get("barcode") == variant.barcode:
#                 return row

#             if variant.variant_name:
#                 if variant.variant_name.lower() in row.get("name","").lower():
#                     return row

#     return None