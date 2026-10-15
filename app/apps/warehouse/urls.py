from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryDocumentViewSet,
    ScannerCreateAndAddAPIView,
    ScannerFindByBarcodeOrSkuAPIView,
    StockMovementViewSet,
    SupplierViewSet,
    WarehouseViewSet,
    scanner_mock_view,
)

app_name = "warehouse"

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"stock-movements", StockMovementViewSet, basename="stock-movements")
router.register(r"inventory-documents", InventoryDocumentViewSet, basename="inventorydocument")

urlpatterns = [
    # Эндпоинты сканера объявлены до роутера, чтобы не пересекаться с detail-маршрутами
    path("stock-movements/find_by_barcode_or_sku/", ScannerFindByBarcodeOrSkuAPIView.as_view(), name="scanner_find"),
    path("stock-movements/create_and_add/", ScannerCreateAndAddAPIView.as_view(), name="scanner_create"),
    path("variants/create-from-scanner/", ScannerCreateAndAddAPIView.as_view(), name="create_from_scanner"),
    path("scanner-test/", scanner_mock_view, name="scanner_test"),
    path("", include(router.urls)),
]
