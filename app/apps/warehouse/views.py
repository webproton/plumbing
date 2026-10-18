from decimal import Decimal

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.http import FileResponse, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils.translation import gettext as _
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.products.models import Product, ProductVariant
from app.apps.products.serializers import ProductVariantSerializer

from . import stock
from .inventory.barcode_scanner import find_variant_by_code, scan_barcode
from .models import InventoryDocument, ProductBarcode, StockBalance, StockMovement, Supplier, Warehouse
from .pdf import generate_invoice_pdf
from .permissions import IsWarehouseStaff, IsWarehouseStaffOrReadOnly, get_active_seller
from .serializers import (
    InventoryAdjustmentSerializer,
    InventoryDocumentSerializer,
    ReturnToSupplierSerializer,
    StockBalanceSerializer,
    StockMovementCreateSerializer,
    StockMovementListSerializer,
    SupplierSerializer,
    TransferSerializer,
    WarehouseSerializer,
)
from .services import (
    file_sha256,
    parse_document,
    process_inventory_document,
    set_line_variant,
    suggest_variants,
)

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _flag(value):
    return str(value).lower() in ("1", "true", "yes", "on")


def _seller_warehouses(user):
    if user.is_superuser:
        return Warehouse.objects.all()
    seller = get_active_seller(user)
    return Warehouse.objects.filter(seller=seller) if seller else Warehouse.objects.none()


def _ensure_own_warehouse(user, warehouse):
    if not _seller_warehouses(user).filter(pk=warehouse.pk).exists():
        raise PermissionDenied(_("Склад не принадлежит вашему магазину"))
    return warehouse


def _default_warehouse(user, seller=None):
    qs = _seller_warehouses(user)
    if seller is not None:
        qs = qs.filter(seller=seller)
    return qs.filter(is_default=True).first() or qs.order_by("id").first()


def _variant_card(variant, user, warehouse=None):
    """Карточка товара для сканера: данные варианта + остатки (себестоимость — только сотрудникам)."""
    data = dict(ProductVariantSerializer(variant).data)
    data.update(
        {
            "status": "found",
            "variant_id": variant.id,
            "name": variant.variant_name or variant.product.name,
            "sku": variant.code,
            "barcode": variant.barcode,
            "cost_price": variant.cost_price,
            "stock_total": variant.stock,
            "reserved": variant.reserved,
            "available": variant.available_stock,
            "stock_current": stock.get_balance(variant, warehouse) if warehouse else None,
        }
    )
    last_in = (
        StockMovement.objects.filter(variant=variant, movement_type=StockMovement.IN)
        .select_related("supplier")
        .order_by("-created_at")
        .first()
    )
    if last_in:
        data["last_supplier"] = last_in.supplier.name if last_in.supplier else None
        data["last_delivery_date"] = last_in.created_at.strftime("%d.%m.%Y")
        data["last_document_number"] = last_in.document_number
    return data


def _create_variant(request, *, name, barcode, sku, price, cost_price, product_id, photo=None):
    seller = get_active_seller(request.user)
    if product_id:
        product = get_object_or_404(Product, pk=product_id)
        if not request.user.is_superuser and product.seller_id not in (None, getattr(seller, "pk", None)):
            raise PermissionDenied(_("Товар принадлежит другому продавцу"))
    else:
        product = Product.objects.create(name=name, seller=seller)
    variant = ProductVariant.objects.create(
        product=product,
        variant_name=name,
        code=sku or None,
        barcode=barcode,
        price=Decimal(str(price or 0)),
        cost_price=Decimal(str(cost_price or 0)),
        photo=photo,
        available=False,  # новый товар скрыт из каталога до проверки карточки
    )
    ProductBarcode.objects.get_or_create(code=str(barcode).strip(), defaults={"variant": variant})
    return variant


# ---------------------------------------------------------------------------
# Сканер
# ---------------------------------------------------------------------------


class ScannerFindByBarcodeOrSkuAPIView(APIView):
    """POST {query, warehouse?} → карточка товара с остатками."""

    permission_classes = [IsWarehouseStaff]

    def post(self, request):
        query = request.data.get("query")
        if not query:
            return Response({"detail": _("Параметр query обязателен")}, status=status.HTTP_400_BAD_REQUEST)
        variant = find_variant_by_code(query)
        if not variant:
            return Response(
                {"status": "not_found", "query": query, "detail": _("Товар не найден")},
                status=status.HTTP_404_NOT_FOUND,
            )
        warehouse_id = request.data.get("warehouse")
        warehouse = (
            _seller_warehouses(request.user).filter(pk=warehouse_id).first()
            if warehouse_id
            else _default_warehouse(request.user)
        )
        return Response(_variant_card(variant, request.user, warehouse))


class ScannerCreateAndAddAPIView(APIView):
    """
    Создание нового товара со сканера. Если переданы document и warehouse —
    сразу приходуется указанное количество по этому документу.
    """

    permission_classes = [IsWarehouseStaff]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @transaction.atomic
    def post(self, request):
        data = request.data
        name = data.get("variant_name") or data.get("name")
        sku = (data.get("sku") or data.get("code") or "").strip()
        barcode = (data.get("barcode") or "").strip() or sku
        if not barcode or not name:
            return Response(
                {"detail": _("Поля barcode (или sku) и name обязательны")}, status=status.HTTP_400_BAD_REQUEST
            )
        for code in {barcode, sku} - {""}:
            if find_variant_by_code(code):
                return Response(
                    {"detail": _("Товар с кодом {code} уже существует").format(code=code)},
                    status=status.HTTP_409_CONFLICT,
                )

        variant = _create_variant(
            request,
            name=name,
            barcode=barcode,
            sku=sku,
            price=data.get("price"),
            cost_price=data.get("cost_price"),
            product_id=data.get("product"),
            photo=request.FILES.get("photo"),
        )

        document_id = data.get("document")
        if document_id:
            document = get_object_or_404(InventoryDocument, pk=document_id)
            if not request.user.is_superuser and document.seller_id != get_active_seller(request.user).pk:
                raise PermissionDenied(_("Документ принадлежит другому продавцу"))
            warehouse = _ensure_own_warehouse(request.user, get_object_or_404(Warehouse, pk=data.get("warehouse")))
            stock.receive(
                variant,
                warehouse,
                data.get("quantity", 1),
                user=request.user,
                supplier=document.supplier,
                inventory_document=document,
                document_number=document.document_number,
                price_per_unit=variant.cost_price,
                comment="Новый товар со сканера",
            )
            variant.refresh_from_db()
            return Response(_variant_card(variant, request.user, warehouse), status=status.HTTP_201_CREATED)

        return Response(_variant_card(variant, request.user), status=status.HTTP_201_CREATED)


@staff_member_required
def scanner_mock_view(request):
    """Тестовая страница физического сканера (только для персонала)."""
    return render(request, "warehouse/scanner_mock.html")


# ---------------------------------------------------------------------------
# Справочники
# ---------------------------------------------------------------------------


class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [IsWarehouseStaffOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Supplier.objects.all()
        return Supplier.objects.filter(is_active=True)

    def perform_destroy(self, instance):
        # Поставщик фигурирует в истории движений — не удаляем, а деактивируем.
        instance.is_active = False
        instance.save(update_fields=["is_active"])


class WarehouseViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseSerializer
    permission_classes = [IsWarehouseStaff]

    def get_queryset(self):
        return _seller_warehouses(self.request.user)

    def perform_create(self, serializer):
        seller = get_active_seller(self.request.user)
        if seller is None:
            raise PermissionDenied(_("Создавать склады может только одобренный продавец"))
        serializer.save(seller=seller)

    def perform_destroy(self, instance):
        if StockMovement.objects.filter(warehouse=instance).exists():
            raise PermissionDenied(_("По складу есть движения — удалить нельзя"))
        instance.delete()

    @action(detail=True, methods=["get"])
    def balances(self, request, pk=None):
        warehouse = self.get_object()
        qs = StockBalance.objects.filter(warehouse=warehouse, quantity__gt=0).select_related("variant", "warehouse")
        page = self.paginate_queryset(qs)
        serializer = StockBalanceSerializer(page if page is not None else qs, many=True)
        return self.get_paginated_response(serializer.data) if page is not None else Response(serializer.data)


# ---------------------------------------------------------------------------
# Журнал движений (только чтение + операции через сервис)
# ---------------------------------------------------------------------------


class StockMovementViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Журнал неизменяем: нет update/delete. Ошибки исправляются встречным движением
    или инвентаризацией.
    """

    permission_classes = [IsWarehouseStaff]
    serializer_class = StockMovementListSerializer
    filterset_fields = ["movement_type", "warehouse", "variant", "inventory_document"]

    def get_queryset(self):
        qs = StockMovement.objects.select_related("variant", "seller", "warehouse", "supplier", "created_by")
        if self.request.user.is_superuser:
            return qs
        seller = get_active_seller(self.request.user)
        return qs.filter(seller=seller) if seller else qs.none()

    def create(self, request, *args, **kwargs):
        """Ручная операция: приход / расход / возврат от клиента / возврат поставщику."""
        serializer = StockMovementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = dict(serializer.validated_data)
        warehouse = _ensure_own_warehouse(request.user, data.pop("warehouse"))
        variant = data.pop("variant")
        quantity = data.pop("quantity")
        movement_type = data.pop("movement_type")
        if movement_type in (StockMovement.IN, StockMovement.RETURN_IN):
            movement = stock.receive(
                variant, warehouse, quantity, user=request.user, movement_type=movement_type, **data
            )
        else:
            movement = stock.write_off(
                variant, warehouse, quantity, user=request.user, movement_type=movement_type, **data
            )
        return Response(StockMovementListSerializer(movement).data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def summary(self, request):
        qs = self.get_queryset()
        last = qs.order_by("-created_at").first()
        return Response(
            {
                "total_in": qs.filter(movement_type=StockMovement.IN).count(),
                "total_out": qs.filter(movement_type=StockMovement.OUT).count(),
                "last_movement": last.created_at if last else None,
            }
        )

    @action(detail=False, methods=["post"])
    def transfer(self, request):
        s = TransferSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        src = _ensure_own_warehouse(request.user, s.validated_data["from_warehouse"])
        dst = _ensure_own_warehouse(request.user, s.validated_data["to_warehouse"])
        stock.transfer(s.validated_data["variant"], src, dst, s.validated_data["quantity"], user=request.user)
        return Response({"status": "transferred"})

    @action(detail=False, methods=["post"])
    def return_supplier(self, request):
        s = ReturnToSupplierSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        warehouse = _ensure_own_warehouse(request.user, s.validated_data["warehouse"])
        stock.return_to_supplier(
            s.validated_data["variant"],
            warehouse,
            s.validated_data["supplier"],
            s.validated_data["quantity"],
            user=request.user,
        )
        return Response({"status": "returned"})

    @action(detail=False, methods=["post"])
    def inventory(self, request):
        s = InventoryAdjustmentSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        warehouse = _ensure_own_warehouse(request.user, s.validated_data["warehouse"])
        movement = stock.adjust(s.validated_data["variant"], warehouse, s.validated_data["quantity"], user=request.user)
        return Response({"status": "inventory done", "changed": movement is not None})


# ---------------------------------------------------------------------------
# Накладные
# ---------------------------------------------------------------------------


class InventoryDocumentViewSet(viewsets.ModelViewSet):
    serializer_class = InventoryDocumentSerializer
    permission_classes = [IsWarehouseStaff]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        qs = InventoryDocument.objects.select_related("seller", "supplier")
        if self.request.user.is_superuser:
            return qs
        seller = get_active_seller(self.request.user)
        return qs.filter(seller=seller) if seller else qs.none()

    def perform_create(self, serializer):
        """Загрузка файла: защита от повторной загрузки по SHA-256 и сразу разбор строк."""
        seller = get_active_seller(self.request.user)
        if seller is None:
            raise PermissionDenied(_("Загружать накладные может только одобренный продавец"))
        digest = file_sha256(serializer.validated_data["file"])
        duplicate = InventoryDocument.objects.filter(seller=seller, file_hash=digest).first()
        if duplicate:
            raise ValidationError(
                {
                    "file": _("Этот файл уже загружен (документ #{pk})").format(pk=duplicate.pk),
                    "document_id": duplicate.pk,
                }
            )
        document = serializer.save(seller=seller, file_hash=digest)
        try:
            parse_document(document)
        except Exception as exc:  # битый/нераспознанный файл: документ остаётся, оператор видит причину
            InventoryDocument.objects.filter(pk=document.pk).update(extracted_data={"error": str(exc)})
        serializer.instance.refresh_from_db()

    def perform_update(self, serializer):
        if serializer.instance.processed:
            raise PermissionDenied(_("Проведённый документ изменять нельзя"))
        serializer.save()

    @action(detail=True, methods=["get"])
    def print(self, request, pk=None):
        document = self.get_object()
        response = HttpResponse(generate_invoice_pdf(document), content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="invoice_{document.pk}.pdf"'
        return response

    @action(detail=True, methods=["get"])
    def file(self, request, pk=None):
        """Скачать исходный файл накладной (файлы не лежат в публичном /media/)."""
        document = self.get_object()
        return FileResponse(
            document.file.open("rb"), as_attachment=True, filename=document.file.name.rsplit("/", 1)[-1]
        )

    @action(detail=True, methods=["post"])
    def parse(self, request, pk=None):
        """Разобрать файл заново (например, после указания поставщика)."""
        document = self.get_object()
        parse_document(document)
        document.refresh_from_db()
        return Response(self.get_serializer(document).data)

    @action(detail=True, methods=["post"], url_path=r"lines/(?P<position>\d+)")
    def set_line(self, request, pk=None, position=None):
        """Сопоставить строку: {"variant": id} или {"create_new": true}."""
        document = self.get_object()
        line = set_line_variant(
            document,
            int(position),
            variant_id=request.data.get("variant"),
            create_new=bool(request.data.get("create_new")),
        )
        return Response(line)

    @action(detail=False, methods=["get"], url_path="variant-search")
    def variant_search(self, request):
        """Подбор товара для ручного сопоставления: ?q=название|артикул|штрихкод"""
        variants = suggest_variants(request.query_params.get("q"))
        return Response(
            [
                {"id": v.pk, "name": v.variant_name or v.product.name, "sku": v.code, "barcode": v.barcode}
                for v in variants
            ]
        )

    @action(detail=True, methods=["post"])
    def process(self, request, pk=None):
        """
        Провести документ. Параметры: warehouse (по умолчанию — основной склад),
        accept_suggestions (принять похожие совпадения без проверки),
        allow_duplicate_number (провести, даже если накладная с таким номером уже проведена).
        """
        document = self.get_object()
        warehouse_id = request.data.get("warehouse")
        if warehouse_id:
            warehouse = _ensure_own_warehouse(request.user, get_object_or_404(Warehouse, pk=warehouse_id))
        else:
            warehouse = _default_warehouse(request.user, seller=document.seller)
        if warehouse is None:
            return Response({"detail": _("У продавца нет склада")}, status=status.HTTP_400_BAD_REQUEST)
        report = process_inventory_document(
            document=document,
            warehouse=warehouse,
            created_by=request.user,
            accept_suggestions=_flag(request.data.get("accept_suggestions")),
            allow_duplicate_number=_flag(request.data.get("allow_duplicate_number")),
        )
        return Response({"status": "document processed", **report})

    @action(detail=True, methods=["post"])
    def scan(self, request, pk=None):
        """Пик сканера в процессе приёмки: +1 единица товара по документу."""
        document = self.get_object()
        if document.processed:
            return Response({"detail": _("Документ уже проведён")}, status=status.HTTP_400_BAD_REQUEST)
        barcode = request.data.get("barcode")
        warehouse_id = request.data.get("warehouse")
        if not barcode or not warehouse_id:
            return Response({"detail": _("barcode и warehouse обязательны")}, status=status.HTTP_400_BAD_REQUEST)
        warehouse = _seller_warehouses(request.user).filter(pk=warehouse_id).first()
        if warehouse is None:
            raise NotFound(_("Склад не найден"))
        try:
            variant = scan_barcode(document=document, barcode=barcode, warehouse=warehouse, user=request.user)
        except ObjectDoesNotExist:
            return Response(
                {
                    "status": "not_found",
                    "barcode": barcode,
                    "detail": _("Товар не зарегистрирован. Открыть форму создания?"),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        doc_qty = sum(m.quantity for m in StockMovement.objects.filter(inventory_document=document, variant=variant))
        return Response(
            {
                "status": "success",
                "variant_id": variant.id,
                "name": variant.variant_name,
                "sku": variant.code,
                "current_doc_qty": doc_qty,
            }
        )
