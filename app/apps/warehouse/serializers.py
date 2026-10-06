from rest_framework import serializers
from .models import Supplier, Warehouse, StockMovement, InventoryDocument
from app.apps.sellers.serializers import SellerListSerializer  # если есть


class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = '__all__'


class WarehouseSerializer(serializers.ModelSerializer):
    seller = serializers.StringRelatedField(read_only=True)

    class Meta:
        model = Warehouse
        fields = '__all__'
        read_only_fields = ['seller', 'created_at']


class StockMovementListSerializer(serializers.ModelSerializer):
    variant_name = serializers.CharField(source='variant.variant_name', read_only=True)
    seller_name = serializers.CharField(source='seller.shop_name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)

    class Meta:
        model = StockMovement
        fields = [
            'id', 'movement_type', 'quantity', 'price_per_unit',
            'document_number', 'comment', 'created_at',
            'variant_name', 'seller_name', 'warehouse_name',
            'supplier_name', 'created_by_email'
        ]


class StockMovementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StockMovement
        fields = [
            'variant', 'warehouse', 'movement_type', 'quantity',
            'price_per_unit', 'document_number', 'supplier', 'comment'
        ]

    def validate(self, data):
        if data['movement_type'] in ['in', 'return_out'] and not data.get('supplier'):
            raise serializers.ValidationError("Для прихода/возврата поставщику нужен поставщик")
        if data['movement_type'] == 'out' and not data.get('variant'):
            raise serializers.ValidationError("Для расхода нужен товар")
        return data


class InventoryDocumentSerializer(serializers.ModelSerializer):
    seller_name = serializers.CharField(source='seller.shop_name', read_only=True)
    linked_movement_id = serializers.PrimaryKeyRelatedField(
        source='linked_movement', read_only=True
    )

    class Meta:
        model = InventoryDocument
        fields = [
            'id', 'document_type', 'file', 'uploaded_at',
            'extracted_data', 'processed', 'linked_movement_id',
            'seller_name'
        ]
        read_only_fields = ['uploaded_at', 'extracted_data', 'processed', 'linked_movement_id']