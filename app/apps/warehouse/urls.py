from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    InventoryDocumentViewSet,
    LabelsView,
    ScannerCreateAndAddAPIView,
    ScannerFindByBarcodeOrSkuAPIView,
    StockBalanceViewSet,
    StockMovementViewSet,
    SupplierPriceDetailView,
    SupplierPricesView,
    SupplierQuoteViewSet,
    SupplierViewSet,
    VariantSearchAPIView,
    WarehouseDashboardAPIView,
    WarehouseMeAPIView,
    WarehouseViewSet,
    scanner_mock_view,
)

app_name = "warehouse"

router = DefaultRouter()
router.register(r"suppliers", SupplierViewSet, basename="supplier")
router.register(r"supplier-quotes", SupplierQuoteViewSet, basename="supplier-quote")
router.register(r"warehouses", WarehouseViewSet, basename="warehouse")
router.register(r"balances", StockBalanceViewSet, basename="balances")
router.register(r"stock-movements", StockMovementViewSet, basename="stock-movements")
router.register(r"inventory-documents", InventoryDocumentViewSet, basename="inventorydocument")

urlpatterns = [
    path("me/", WarehouseMeAPIView.as_view(), name="me"),
    path("dashboard/", WarehouseDashboardAPIView.as_view(), name="dashboard"),
    path("labels/", LabelsView.as_view(), name="labels"),
    path("variants/search/", VariantSearchAPIView.as_view(), name="variant_search"),
    path("supplier-prices/", SupplierPricesView.as_view(), name="supplier_prices"),
    path("supplier-prices/<int:variant_id>/", SupplierPriceDetailView.as_view(), name="supplier_price_detail"),
    # Эндпоинты сканера объявлены до роутера, чтобы не пересекаться с detail-маршрутами
    path("stock-movements/find_by_barcode_or_sku/", ScannerFindByBarcodeOrSkuAPIView.as_view(), name="scanner_find"),
    path("stock-movements/create_and_add/", ScannerCreateAndAddAPIView.as_view(), name="scanner_create"),
    path("variants/create-from-scanner/", ScannerCreateAndAddAPIView.as_view(), name="create_from_scanner"),
    path("scanner-test/", scanner_mock_view, name="scanner_test"),
    path("", include(router.urls)),
]
