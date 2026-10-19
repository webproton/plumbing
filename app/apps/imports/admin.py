from django.contrib import admin

from .models import ImportRun, ImportSource, SupplierItem


@admin.register(ImportSource)
class ImportSourceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "seller",
        "kind",
        "format",
        "sync_interval_minutes",
        "last_sync_at",
        "last_status",
        "is_active",
    )
    list_filter = ("kind", "is_active", "last_status")
    search_fields = ("name", "url")
    # пароль/токен в админке не показываем и не редактируем: только через кабинет (шифруется)
    exclude = ("secret_encrypted",)
    readonly_fields = ("last_sync_at", "next_sync_at", "last_status", "last_error")


@admin.register(SupplierItem)
class SupplierItemAdmin(admin.ModelAdmin):
    list_display = ("name", "source", "sku", "barcode", "price", "cost", "quantity", "status", "missing")
    list_filter = ("status", "missing", "source")
    search_fields = ("name", "sku", "barcode", "external_id")
    raw_id_fields = ("variant",)
    list_select_related = ("source",)


@admin.register(ImportRun)
class ImportRunAdmin(admin.ModelAdmin):
    list_display = ("id", "kind", "status", "seller", "source", "file_name", "created_at", "finished_at")
    list_filter = ("kind", "status")
    exclude = ("rows",)
    readonly_fields = ("stats", "error", "options")
