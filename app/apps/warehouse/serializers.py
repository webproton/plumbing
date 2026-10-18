import os
from decimal import Decimal

from django.utils.translation import gettext as _
from rest_framework import serializers

from app.apps.products.models import ProductVariant

from .models import InventoryDocument, StockBalance, StockMovement, Supplier, Warehouse

ALLOWED_INVOICE_EXTENSIONS = {".xlsx", ".xls", ".xml", ".yml"}
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
    variant_name = serializers.CharField(source="variant.variant_name", read_only=True)
    warehouse_name = serializers.CharField(source="warehouse.name", read_only=True)

    class Meta:
        model = StockBalance
        fields = ["id", "variant", "variant_name", "warehouse", "warehouse_name", "quantity", "updated_at"]


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
            "processed",
            "processed_at",
            "movements_count",
            "seller_name",
        ]
        read_only_fields = ["uploaded_at", "extracted_data", "processed", "processed_at"]
        extra_kwargs = {"file": {"write_only": True}}

    def get_summary(self, obj):
        return (obj.extracted_data or {}).get("summary")

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
