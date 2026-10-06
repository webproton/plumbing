from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    CreateVariantFromScannerAPIView, ScannerCreateAndAddAPIView, ScannerFindByBarcodeOrSkuAPIView, SupplierViewSet, WarehouseViewSet,
    StockMovementViewSet, InventoryDocumentViewSet, scanner_mock_view
)
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
app_name = "warehouse"

router = DefaultRouter()
router.register(r'suppliers', SupplierViewSet, basename='supplier')
router.register(r'warehouses', WarehouseViewSet, basename='warehouse')
router.register(r'stock-movements', StockMovementViewSet, basename='stock-movements')
router.register(r'inventory-documents', InventoryDocumentViewSet, basename='inventorydocument')

# Вытаскиваем экшены ViewSet вручную, чтобы связать их с конкретными URL
stock_movement_custom_actions = StockMovementViewSet.as_view(
    {'post': 'create_and_add'},
    parser_classes=[MultiPartParser, FormParser, JSONParser] # 🔥 Передаем сюда принудительно!
)

stock_movement_search_action = StockMovementViewSet.as_view({
    'post': 'find_by_barcode_or_sku'
})

urlpatterns = [
    # 🔥 ЖЕСТКИЙ ФИКС: Явные урлы для сканера (идут ПЕРВЫМИ, до роутера)
    # path('stock-movements/create_and_add/', stock_movement_custom_actions, name='stock_movements_create_and_add'),
    # path('stock-movements/find_by_barcode_or_sku/', stock_movement_search_action, name='stock_movements_find_by_barcode_or_sku'),
    
    path('stock-movements/create_and_add/', ScannerCreateAndAddAPIView.as_view(), name='stock_movements_create_and_add'),
    path('stock-movements/find_by_barcode_or_sku/', ScannerFindByBarcodeOrSkuAPIView.as_view(), name='stock_movements_find_by_barcode_or_sku'),
    
    # Все остальные стандартные роуты (list, retrieve, и т.д.)
    path('', include(router.urls)),
    
    path('variants/create-from-scanner/', CreateVariantFromScannerAPIView.as_view(), name='create_from_scanner'),
    path('scanner-test/', scanner_mock_view, name='scanner_test'),
]


# http://127.0.0.1:8000/warehouse/scanner-test/