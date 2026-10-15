from django.contrib import admin, messages
from django.db.models import F, Sum

from . import stock
from .models import InventoryDocument, StockBalance, StockMovement, Supplier, Warehouse
from .services import ReviewRequiredError, process_inventory_document


@admin.action(description="Провести на склад (парсинг + сопоставление)")
def accept_document(modeladmin, request, queryset):
    for document in queryset.select_related("seller"):
        if document.processed:
            continue
        warehouse = (
            Warehouse.objects.filter(seller=document.seller, is_default=True).first()
            or Warehouse.objects.filter(seller=document.seller).order_by("id").first()
        )
        if not warehouse:
            modeladmin.message_user(request, f"У продавца {document.seller} нет склада", level=messages.ERROR)
            continue
        try:
            report = process_inventory_document(document=document, warehouse=warehouse, created_by=request.user)
        except ReviewRequiredError as exc:
            modeladmin.message_user(
                request,
                f"Документ {document.pk}: {exc.message}. Сопоставьте строки через API/кабинет склада.",
                level=messages.WARNING,
            )
            continue
        except Exception as exc:  # показываем оператору причину, остальные документы обрабатываем дальше
            modeladmin.message_user(request, f"Документ {document.pk}: ошибка — {exc}", level=messages.ERROR)
            continue
        msg = (
            f"Документ №{document.document_number or document.pk}: оприходовано строк {report['received']}, "
            f"создано новых товаров {report['created']}"
        )
        if report["skipped"]:
            msg += f", пропущено {len(report['skipped'])} (см. extracted_data.processing_report)"
        modeladmin.message_user(request, msg, level=messages.WARNING if report["skipped"] else messages.SUCCESS)


@admin.action(description="Сверить и пересчитать остатки по журналу")
def rebuild_balances(modeladmin, request, queryset):
    variant_ids = set(queryset.values_list("variant_id", flat=True))
    for variant_id in sorted(variant_ids):
        stock.rebuild_from_journal(variant_id)
    modeladmin.message_user(request, f"Пересчитано вариантов: {len(variant_ids)}")


class ReadOnlyAdminMixin:
    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "contact_person", "phone", "email", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "contact_person", "email", "phone")
    ordering = ("name",)


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ("name", "seller", "address", "is_default", "created_at")
    list_filter = ("is_default", "seller")
    search_fields = ("name", "seller__shop_name", "address")
    ordering = ("seller", "name")


@admin.register(StockBalance)
class StockBalanceAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("variant", "warehouse", "quantity", "updated_at")
    list_filter = ("warehouse",)
    search_fields = ("variant__variant_name", "variant__code", "variant__barcode")
    list_select_related = ("variant", "warehouse")


class StockMovementInline(ReadOnlyAdminMixin, admin.TabularInline):
    model = StockMovement
    extra = 0
    fields = ("variant", "quantity", "movement_type", "price_per_unit", "warehouse", "supplier", "created_by")
    readonly_fields = fields


@admin.register(StockMovement)
class StockMovementAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    """Журнал только для чтения: операции выполняются через API склада / сканер."""

    list_display = (
        "variant",
        "seller",
        "warehouse",
        "movement_type",
        "quantity",
        "price_per_unit",
        "supplier",
        "created_at",
        "created_by",
    )
    list_filter = ("movement_type", "seller", "warehouse", "supplier")
    search_fields = ("variant__variant_name", "variant__code", "document_number")
    list_select_related = ("variant", "seller", "warehouse", "supplier", "created_by")
    ordering = ("-created_at",)
    actions = [rebuild_balances]


@admin.register(InventoryDocument)
class InventoryDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "document_number",
        "document_type",
        "seller",
        "supplier",
        "uploaded_at",
        "processed",
        "skipped_rows",
        "movements_count",
        "total_sum",
    )
    list_filter = ("document_type", "processed", "seller")
    search_fields = ("document_number", "seller__shop_name")
    ordering = ("-uploaded_at",)
    inlines = [StockMovementInline]
    actions = [accept_document]

    def get_readonly_fields(self, request, obj=None):
        return ("processed", "processed_at", "file_hash", "extracted_data") + (
            ("file", "seller", "supplier") if obj and obj.processed else ()
        )

    @admin.display(description="Пропущено строк")
    def skipped_rows(self, obj):
        report = (obj.extracted_data or {}).get("processing_report") or {}
        return len(report.get("skipped", []))

    @admin.display(description="Движений")
    def movements_count(self, obj):
        return obj.stock_movements.count()

    @admin.display(description="Сумма")
    def total_sum(self, obj):
        return obj.stock_movements.aggregate(total=Sum(F("quantity") * F("price_per_unit")))["total"] or 0
