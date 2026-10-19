import os
from decimal import Decimal

from django.utils.translation import gettext as _
from rest_framework import serializers

from app.apps.products.models import ProductVariant

from .models import InventoryDocument, StockBalance, StockMovement, Supplier, Warehouse

ALLOWED_INVOICE_EXTENSIONS = {".xlsx", ".xls", ".xml", ".yml", ".pdf", ".jpg", ".jpeg", ".png", ".webp"}
MAX_INVOICE_SIZE = 10 * 1024 * 1024  # 10 МБ


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = "__all__"


class WarehouseSerializer(serializers.ModelSerializer):
    seller = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Warehouse
        fields = "__all__"
        read_only_fields = ["seller", "created_at"]


class StockBalanceSerializer(serializers.ModelSerializer):
    variant_name = serializers.SerializerMethodField()
    sku = serializers.CharField(source="variant.code", read_only=True, default=None)
    barcode = serializers.CharField(source="variant.barcode", read_only=True, default=None)
    cost_price = serializers.DecimalField(
        source="variant.cost_price", max_digits=12, decimal_places=4, read_only=True, default=None
    )
    price = serializers.DecimalField(
        source="variant.price", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    reserved = serializers.DecimalField(source="variant.reserved", max_digits=12, decimal_places=3, read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    value = serializers.SerializerMethodField(help_text="Сумма остатка по себестоимости")

    class Meta:
        model = StockBalance
        fields = [
            "id", "variant", "variant_name", "sku", "barcode", "warehouse", "warehouse_name",
            "quantity", "reserved", "cost_price", "price", "value", "updated_at",
        ]  # fmt: skip

    def get_variant_name(self, obj):
        return obj.variant.variant_name or (obj.variant.product.name if obj.variant.product_id else "")

    def get_value(self, obj):
        cost = obj.variant.cost_price
        return str((obj.quantity * cost).quantize(Decimal("0.01"))) if cost is not None else None


class VariantLookupSerializer(serializers.ModelSerializer):
    """Короткая карточка товара для выбора в формах склада."""

    name = serializers.SerializerMethodField()
    sku = serializers.CharField(source="code", read_only=True)
    available = serializers.DecimalField(source="available_stock", max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = ProductVariant
        fields = ["id", "name", "sku", "barcode", "cost_price", "price", "stock", "reserved", "available"]

    def get_name(self, obj):
        return obj.variant_name or (obj.product.name if obj.product_id else "")


class StockMovementListSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source="variant.variant_name", read_only=True)
    seller_name = serializers.CharField(source="seller.shop_name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = StockMovement
        fields = [
            "id",
            "movement_type",
            "quantity",
            "price_per_unit",
            "document_number",
            "comment",
            "created_at",
            "variant",
            "variant_name",
            "seller_name",
            "warehouse",
            "warehouse_name",
            "supplier_name",
            "created_by_email",
        ]


class StockMovementCreateSerializer(serializers.Serializer):
    """Ручная складская операция. Перемещение и инвентаризация — отдельные эндпоинты."""

    MANUAL_TYPES = [StockMovement.IN, StockMovement.OUT, StockMovement.RETURN_IN, StockMovement.RETURN_OUT]

    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    movement_type = serializers.ChoiceField(choices=MANUAL_TYPES)
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))
    price_per_unit = serializers.DecimalField(max_digits=12, decimal_places=4, required=False, allow_null=True)
    document_number = serializers.CharField(max_length=50, required=False, allow_blank=True)
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all(), required=False, allow_null=True)
    comment = serializers.CharField(required=False, allow_blank=True)

    def validate(self, data):
        if data["movement_type"] in (StockMovement.IN, StockMovement.RETURN_OUT) and not data.get("supplier"):
            raise serializers.ValidationError({"supplier": _("Для прихода/возврата поставщику нужен поставщик")})
        return data


class TransferSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    from_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    to_warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))


class ReturnToSupplierSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    supplier = serializers.PrimaryKeyRelatedField(queryset=Supplier.objects.all())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0.001"))


class InventoryAdjustmentSerializer(serializers.Serializer):
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all())
    warehouse = serializers.PrimaryKeyRelatedField(queryset=Warehouse.objects.all())
    quantity = serializers.DecimalField(max_digits=12, decimal_places=3, min_value=Decimal("0"))


class InventoryDocumentSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source="seller.shop_name", read_only=True)
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)
    movements_count = serializers.IntegerField(source="stock_movements.count", read_only=True)
    summary = serializers.SerializerMethodField(help_text="Количество строк по статусам сопоставления")
    variants = serializers.SerializerMethodField(
        help_text="Названия товаров из строк: {id: {name, sku}} (только в карточке)"
    )
    ai = serializers.SerializerMethodField(help_text="Разбор через ИИ: включён ли, статус, ошибка")

    class Meta:
        model = InventoryDocument
        fields = [
            "id",
            "document_type",
            "document_number",
            "supplier",
            "supplier_name",
            "file",
            "uploaded_at",
            "extracted_data",
            "summary",
            "variants",
            "processed",
            "processed_at",
            "movements_count",
            "seller_name",
            "column_map",
            "ai",
        ]
        read_only_fields = ["uploaded_at", "extracted_data", "processed", "processed_at", "column_map"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_ai(self, obj):
        from .services import ai_enabled

        return {
            "enabled": ai_enabled(),
            "status": obj.ai_status,
            "error": obj.ai_error,
            "has_result": bool(obj.ai_result),
        }

    def get_summary(self, obj):
        return (obj.extracted_data or {}).get("summary")

    def get_variants(self, obj):
        """Названия товаров, на которые ссылаются строки (id и кандидаты); в списке не считаем — N+1."""
        view = self.context.get("view")
        if getattr(view, "action", None) == "list":
            return {}
        lines = (obj.extracted_data or {}).get("lines") or []
        ids = {ln["variant_id"] for ln in lines if ln.get("variant_id")}
        ids |= {c["variant_id"] for ln in lines for c in ln.get("candidates", [])}
        if not ids:
            return {}
        found = ProductVariant.objects.filter(pk__in=ids).select_related("product")
        return {
            str(v.pk): {"name": v.variant_name or (v.product.name if v.product_id else ""), "sku": v.code}
            for v in found
        }

    def validate_file(self, f):
        ext = os.path.splitext(f.name)[1].lower()
        if ext not in ALLOWED_INVOICE_EXTENSIONS:
            raise serializers.ValidationError(
                _("Неподдерживаемый формат {ext}. Допустимы: {allowed}").format(
                    ext=ext or _("(без расширения)"), allowed=", ".join(sorted(ALLOWED_INVOICE_EXTENSIONS))
                )
            )
        if f.size > MAX_INVOICE_SIZE:
            raise serializers.ValidationError(_("Файл больше 10 МБ"))
        return f
