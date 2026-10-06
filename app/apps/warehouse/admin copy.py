from django.contrib import admin

from app.apps.warehouse.parsers import learn_variant_match
# Register your models here.
# admin.site.register(Warehouse)
from .models import Supplier, Warehouse, StockMovement, InventoryDocument
from app.apps.products.models import ProductVariant
from django.db import transaction
from django.db.models import Sum, F, Q
# from .services import process_inventory_document, extract_document_data

from .services import process_inventory_document


@admin.action(description="Принять на склад (Новый парсер + Обучение)")
def accept_document(modeladmin, request, queryset):
    """
    Вызывает единый сервис, который сделает всё красиво и безопасно
    """
    for document in queryset:
        if document.processed:
            continue
            
        # Находим склад продавца
        warehouse = Warehouse.objects.filter(seller=document.seller, is_default=True).first()
        if not warehouse:
            warehouse = Warehouse.objects.filter(seller=document.seller).first()
            
        if not warehouse:
            modeladmin.message_user(request, f"У продавца {document.seller} не найден склад!", level='ERROR')
            continue

        try:
            # Вызов единой точки входа бизнес-логики
            process_inventory_document(
                document=document,
                warehouse=warehouse,
                created_by=request.user
            )
        except Exception as e:
            modeladmin.message_user(request, f"Ошибка обработки документа {document.id}: {e}", level='ERROR')

# @admin.action(description="Принять на склад (OCR + движения + обучение)")
# def accept_document(modeladmin, request, queryset):

#     for document in queryset:
#         if document.processed:
#             continue

#         with transaction.atomic():

#             # 1. Парсинг + enrichment (matching)
#             extract_document_data(document)

#             data = document.extracted_data or {}
#             rows = data.get("tables", [{}])[0].get("rows", [])
#             errors = data.get("errors", [])

#             warehouse = Warehouse.objects.filter(seller=document.seller).first()

#             # 2. Создание движений + обучение
#             for row in rows:

#                 variant = row.get("variant_id")
#                 confidence = row.get("confidence", 0)

#                 if not variant:
#                     continue

#                 variant_obj = None
#                 try:
#                     from app.apps.products.models import ProductVariant
#                     variant_obj = ProductVariant.objects.get(id=variant)
#                 except:
#                     continue

#                 # движение
#                 process_inventory_document(
#                     document=document,
#                     warehouse=warehouse,
#                     created_by=request.user,
#                     row=row
#                 )

#                 # 🔥 ОБУЧЕНИЕ (1С логика)
#                 learn_variant_match(
#                     row=row,
#                     variant=variant_obj,
#                     supplier=document.supplier
#                 )

#             # 3. флаги качества
#             document.processed = True

#             if errors:
#                 document.extracted_data["has_errors"] = True

#             document.save()


        
        
# @admin.action(description="Обработать без обучения")
# def process_document(modeladmin, request, queryset):
#     for doc in queryset:
#         warehouse = doc.seller.warehouses.filter(is_default=True).first()

#         process_inventory_document(
#             doc,
#             warehouse,
#             request.user
#         )
        
@admin.action(description="Принудительно пересчитать (без проверки флага processed)")
def process_document(modeladmin, request, queryset):
    for document in queryset:
        warehouse = Warehouse.objects.filter(seller=document.seller, is_default=True).first() or \
                    Warehouse.objects.filter(seller=document.seller).first()
        if warehouse:
            process_inventory_document(document, warehouse, request.user)
        
@admin.action(description="Перемещение между складами")
def transfer_action(modeladmin, request, queryset):
    from .services import transfer_between_warehouses

    for obj in queryset:
        if not obj.target_warehouse:
            continue

        transfer_between_warehouses(
            variant=obj.variant,
            from_warehouse=obj.warehouse,
            to_warehouse=obj.target_warehouse,
            quantity=obj.quantity,
            user=request.user
        )


@admin.action(description="Возврат поставщику")
def return_supplier_action(modeladmin, request, queryset):
    from .services import return_to_supplier

    for obj in queryset:
        if not obj.supplier:
            continue

        return_to_supplier(
            variant=obj.variant,
            warehouse=obj.warehouse,
            supplier=obj.supplier,
            quantity=obj.quantity,
            user=request.user
        )


@admin.action(description="Инвентаризация склада")
def inventory_action(modeladmin, request, queryset):
    from .services import inventory_adjustment

    for obj in queryset:
        inventory_adjustment(
            variant=obj.variant,
            warehouse=obj.warehouse,
            real_quantity=obj.quantity,
            user=request.user
        )


@admin.action(description="Распечатать PDF накладную")
def print_invoice(modeladmin, request, queryset):
    from .pdf import generate_invoice_pdf

    for doc in queryset:
        generate_invoice_pdf(doc)

# === Supplier ===
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_person', 'email', 'phone')
    ordering = ('name',)

# === Warehouse ===
@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'address', 'is_default', 'created_at')
    list_filter = ('is_default', 'seller')
    search_fields = ('name', 'seller__shop_name', 'address')
    ordering = ('seller', 'name')
    
    
    readonly_fields = ['current_stock']

    def current_stock(self, obj):
        stock = {}
        variants = ProductVariant.objects.filter(movements__warehouse=obj).distinct()
        for v in variants:
            balance = v.movements.filter(warehouse=obj).aggregate(
                total_in=Sum('quantity', filter=Q(movement_type__in=['in','return_in','adjustment'])),
                total_out=Sum('quantity', filter=Q(movement_type__in=['out','return_out','transfer']))
            )
            stock[v.variant_name] = (balance['total_in'] or 0) - (balance['total_out'] or 0)
        return stock
    current_stock.short_description = "Текущий остаток"
    
    

# === StockMovement Inline ===
class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    fields = ('variant', 'quantity', 'movement_type', 'price_per_unit', 'total_price','warehouse', 'supplier', 'created_by')
    readonly_fields = ('created_by','total_price')
    
    
    def total_price(self, obj):
        if obj.quantity and obj.price_per_unit:
            return obj.quantity * obj.price_per_unit
        return 0
    total_price.short_description = "Сумма"


# === StockMovement ===
@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('variant', 'seller', 'warehouse', 'movement_type', 'quantity', 'price_per_unit', 'supplier', 'created_at', 'created_by')
    list_filter = ('movement_type', 'seller', 'warehouse', 'supplier')
    search_fields = ('variant__variant_name', 'seller__shop_name', 'warehouse__name', 'document_number')
    ordering = ('-created_at',)
    
    actions = [
        transfer_action,
        return_supplier_action,
        inventory_action,
        "delete_selected"
    ]

# === InventoryDocument ===
@admin.register(InventoryDocument)
class InventoryDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'document_type', 'seller', 'file', 'uploaded_at', 'processed', 'errors_count',
    'risk_level',
        'linked_movements_count', 'total_quantity', 'total_sum'
    )
    list_filter = ('document_type', 'processed', 'seller')
    search_fields = ('seller__shop_name', 'file')
    ordering = ('-uploaded_at',)
    
    inlines = [StockMovementInline]  # подключаем inline
    actions = [
    accept_document,        # главное действие
    process_document,       # пересборка
    transfer_action,
    return_supplier_action,
    inventory_action,
    print_invoice,
]
    
    
        
    @admin.display(description="Ошибки")
    def errors_count(self, obj):
        data = obj.extracted_data or {}
        return len(data.get("errors", []))


    @admin.display(description="Риск")
    def risk_level(self, obj):
        data = obj.extracted_data or {}
        errors = len(data.get("errors", []))

        if errors == 0:
            return "🟢 OK"
        elif errors < 5:
            return "🟡 WARN"
        return "🔴 BAD"
    
    # Количество связанных движений
    def linked_movements_count(self, obj):
        return obj.stock_movements.all().count() if obj.stock_movements else 0
    linked_movements_count.short_description = "Движений"

    # Подсчет общей суммы и количества для документа
    def total_quantity(self, obj):
        if obj.stock_movements:
            return obj.stock_movements.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        return 0
    total_quantity.short_description = "Всего шт."

    def total_sum(self, obj):
        if obj.stock_movements:
            return obj.stock_movements.aggregate(
                total=Sum(F('quantity') * F('price_per_unit'))
            )['total'] or 0
        return 0
    total_sum.short_description = "Общая сумма"
    
    
    
