from django.contrib import admin
from django.db.models import Sum, F, Q
from django.utils.html import format_html

from app.apps.products.models import ProductVariant
from .models import Supplier, Warehouse, StockMovement, InventoryDocument

# Импортируем наши готовые оптимизированные сервисы
from .services import (
    process_inventory_document, 
    transfer_between_warehouses, 
    return_to_supplier, 
    inventory_adjustment,
    get_variant_stock
)

# ==========================================
# ДОПОЛНИТЕЛЬНЫЕ ДЕЙСТВИЯ (ADMIN ACTIONS)
# ==========================================

@admin.action(description="Принять на склад (Новый парсер + Обучение)")
def accept_document(modeladmin, request, queryset):
    """Единая точка автоматической обработки документов"""
    for document in queryset:
        if document.processed:
            continue
            
        warehouse = Warehouse.objects.filter(seller=document.seller, is_default=True).first() or \
                    Warehouse.objects.filter(seller=document.seller).first()
            
        if not warehouse:
            modeladmin.message_user(request, f"У продавца {document.seller} не найден склад!", level='ERROR')
            continue

        try:
            process_inventory_document(
                document=document,
                warehouse=warehouse,
                created_by=request.user
            )
            modeladmin.message_user(request, f"Документ №{document.document_number or document.id} успешно обработан.")
        except Exception as e:
            modeladmin.message_user(request, f"Ошибка обработки документа {document.id}: {e}", level='ERROR')


@admin.action(description="Принудительно пересчитать (без проверки флага processed)")
def process_document(modeladmin, request, queryset):
    for document in queryset:
        warehouse = Warehouse.objects.filter(seller=document.seller, is_default=True).first() or \
                    Warehouse.objects.filter(seller=document.seller).first()
        if warehouse:
            process_inventory_document(document, warehouse, request.user)
        

@admin.action(description="Перемещение между складами")
def transfer_action(modeladmin, request, queryset):
    for obj in queryset:
        # 🔥 ИСПРАВЛЕНО: Защита от падения, если на модели нет поля target_warehouse
        target_wh = getattr(obj, 'target_warehouse', None)
        if not target_wh:
            modeladmin.message_user(
                request, 
                f"Ошибка: Для перемещения {obj} не указан целевой склад (target_warehouse).", 
                level='ERROR'
            )
            continue

        transfer_between_warehouses(
            variant=obj.variant,
            from_warehouse=obj.warehouse,
            to_warehouse=target_wh,
            quantity=obj.quantity,
            user=request.user
        )


@admin.action(description="Возврат поставщику")
def return_supplier_action(modeladmin, request, queryset):
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


# ==========================================
# РЕГИСТРАЦИЯ МОДЕЛЕЙ В АДМИНКЕ
# ==========================================

@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'phone', 'email', 'is_active', 'created_at')
    list_filter = ('is_active',)
    search_fields = ('name', 'contact_person', 'email', 'phone')
    ordering = ('name',)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'seller', 'address', 'is_default', 'created_at')
    list_filter = ('is_default', 'seller')
    search_fields = ('name', 'seller__shop_name', 'address')
    ordering = ('seller', 'name')
    readonly_fields = ['current_stock_display'] # Переименовали для понятности

    # 🔥 ПОЛНОСТЬЮ ИСПРАВЛЕНО: Используем наш новый быстрый get_variant_stock
    def current_stock_display(self, obj):
        variants = ProductVariant.objects.filter(movements__warehouse=obj).distinct()
        if not variants.exists():
            return "Склад пуст"
        
        html = "<ul>"
        for v in variants:
            balance = get_variant_stock(v, warehouse=obj)
            html += f"<li><b>{v.variant_name}</b>: {balance} шт.</li>"
        html += "</ul>"
        return format_html(html)
    
    current_stock_display.short_description = "Текущие остатки товаров"


class StockMovementInline(admin.TabularInline):
    model = StockMovement
    extra = 0
    fields = ('variant', 'quantity', 'movement_type', 'price_per_unit', 'total_price', 'warehouse', 'supplier', 'created_by')
    readonly_fields = ('created_by', 'total_price')
    
    def total_price(self, obj):
        if obj.quantity and obj.price_per_unit:
            return obj.quantity * obj.price_per_unit
        return 0
    total_price.short_description = "Сумма"


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


@admin.register(InventoryDocument)
class InventoryDocumentAdmin(admin.ModelAdmin):
    list_display = (
        'document_type', 'seller', 'file', 'uploaded_at', 'processed', 'errors_count',
        'risk_level', 'linked_movements_count', 'total_quantity', 'total_sum'
    )
    list_filter = ('document_type', 'processed', 'seller')
    search_fields = ('seller__shop_name', 'file')
    ordering = ('-uploaded_at',)
    inlines = [StockMovementInline]
    actions = [
        accept_document,        
        process_document,       
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
    
    def linked_movements_count(self, obj):
        return obj.stock_movements.count() if obj.pk else 0
    linked_movements_count.short_description = "Движений"

    def total_quantity(self, obj):
        if obj.pk:
            return obj.stock_movements.aggregate(total_qty=Sum('quantity'))['total_qty'] or 0
        return 0
    total_quantity.short_description = "Всего шт."

    def total_sum(self, obj):
        if obj.pk:
            return obj.stock_movements.aggregate(
                total=Sum(F('quantity') * F('price_per_unit'))
            )['total'] or 0
        return 0
    total_sum.short_description = "Общая сумма"