from datetime import date

from django.db.models import Count, Q
from django.http import HttpResponse
from django.utils.translation import gettext as _
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.products.models import Category
from app.apps.warehouse.models import Warehouse
from app.apps.warehouse.permissions import get_active_seller
from app.core.pagination import StandardPagination
from app.core.tasks import QueueUnavailable, enqueue

from . import services, template
from .connectors import ADAPTERS
from .formats import FormatError
from .models import ImportRun, SupplierItem
from .permissions import IsImportStaff
from .serializers import (
    ImportRunSerializer,
    ImportSourceSerializer,
    ItemStatusSerializer,
    LinkSerializer,
    PublishSerializer,
    SupplierItemSerializer,
    TemplateUploadSerializer,
)
from .tasks import apply_template_task, download_photos_task, sync_source_task

QUEUE_DOWN = _("Фоновые задачи временно недоступны, попробуйте через минуту")


def _require_seller(user):
    seller = get_active_seller(user)
    if seller is None:
        raise PermissionDenied(_("Импорт товаров доступен одобренным продавцам"))
    return seller


def _seller_warehouse(seller, warehouse_id):
    if not warehouse_id:
        return None
    warehouse = Warehouse.objects.filter(seller=seller, pk=warehouse_id).first()
    if warehouse is None:
        raise ValidationError({"warehouse": _("Склад не найден")})
    return warehouse


class TemplateDownloadView(APIView):
    """GET ?type=xlsx|csv [&products=1 — заполнить вашими товарами для массового редактирования]."""

    permission_classes = [IsImportStaff]

    def get(self, request):
        fmt = "csv" if request.query_params.get("type") == "csv" else "xlsx"
        with_products = request.query_params.get("products") == "1"
        seller = _require_seller(request.user) if with_products else None
        content, content_type = template.build_template(fmt, seller)
        name = f"products-{date.today():%Y%m%d}" if with_products else "products-template"
        response = HttpResponse(content, content_type=content_type)
        response["Content-Disposition"] = f'attachment; filename="{name}.{fmt}"'
        return response


class AdaptersView(APIView):
    permission_classes = [IsImportStaff]

    def get(self, request):
        return Response(
            [
                {
                    "code": code,
                    "title": str(cls.title),
                    "description": str(cls.description),
                    "options": {k: str(v) for k, v in cls.option_fields.items()},
                }
                for code, cls in sorted(ADAPTERS.items())
            ]
        )


class ImportRunViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    """
    Загрузка шаблона товаров: POST (файл) → предпросмотр (status=preview) → POST apply/ → done.
    Строки предпросмотра — GET rows/?filter=errors|create|update|warnings.
    """

    serializer_class = ImportRunSerializer
    permission_classes = [IsImportStaff]
    pagination_class = StandardPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        qs = ImportRun.objects.select_related("source", "created_by")
        if not self.request.user.is_superuser:
            seller = get_active_seller(self.request.user)
            qs = qs.filter(seller=seller) if seller else qs.none()
        if kind := self.request.query_params.get("kind"):
            qs = qs.filter(kind=kind)
        return qs

    def create(self, request):
        seller = _require_seller(request.user)
        form = TemplateUploadSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        upload = form.validated_data["file"]
        warehouse = _seller_warehouse(seller, form.validated_data.get("warehouse"))
        content = upload.read()
        try:
            rows, columns = template.read_rows(content, upload.name)
        except FormatError as exc:
            raise ValidationError({"file": str(exc)}) from None
        if not rows:
            raise ValidationError({"file": _("В файле нет строк с товарами")})
        rows, stats = template.plan(rows, seller)
        upload.seek(0)
        run = ImportRun.objects.create(
            kind=ImportRun.KIND_TEMPLATE,
            status=ImportRun.PREVIEW,
            seller=seller,
            created_by=request.user,
            file=upload,
            file_name=upload.name[:255],
            options={"warehouse_id": warehouse.pk if warehouse else None, "publish": form.validated_data["publish"]},
            stats={**stats, "columns": columns},
            rows=rows,
        )
        return Response(self.get_serializer(run).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"])
    def rows(self, request, pk=None):
        run = self.get_object()
        flt = request.query_params.get("filter", "all")
        rows = run.rows
        if flt in ("error", "errors"):
            rows = [r for r in rows if r.get("action") == "error"]
        elif flt in ("create", "update"):
            rows = [r for r in rows if r.get("action") == flt]
        elif flt == "warnings":
            rows = [r for r in rows if r.get("warnings")]
        page = self.paginate_queryset(rows)
        return self.get_paginated_response(page)

    @action(detail=True, methods=["post"])
    def apply(self, request, pk=None):
        run = self.get_object()
        seller = run.seller
        options = dict(run.options)
        if "warehouse" in request.data:
            warehouse = _seller_warehouse(seller, request.data.get("warehouse"))
            options["warehouse_id"] = warehouse.pk if warehouse else None
        if "publish" in request.data:
            options["publish"] = str(request.data.get("publish")).lower() in ("1", "true", "on")
        if run.stats.get("stock") and not options.get("warehouse_id"):
            raise ValidationError({"warehouse": _("В файле есть остатки — выберите склад")})

        # защита от двойного нажатия: применить можно только из предпросмотра
        updated = ImportRun.objects.filter(pk=run.pk, status=ImportRun.PREVIEW).update(
            status=ImportRun.APPLYING, options=options
        )
        if not updated:
            raise ValidationError({"detail": _("Этот импорт уже применён или выполняется")})
        try:
            enqueue(apply_template_task, run.pk)
        except QueueUnavailable:
            ImportRun.objects.filter(pk=run.pk).update(status=ImportRun.PREVIEW)
            return Response({"detail": QUEUE_DOWN}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        run.refresh_from_db()
        return Response(self.get_serializer(run).data, status=status.HTTP_202_ACCEPTED)

    def perform_destroy(self, instance):
        if instance.status != ImportRun.PREVIEW:
            raise ValidationError({"detail": _("Удалить можно только неприменённую загрузку")})
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()


class ImportSourceViewSet(viewsets.ModelViewSet):
    """Источники товаров поставщиков + действия с их позициями."""

    serializer_class = ImportSourceSerializer
    permission_classes = [IsImportStaff]
    pagination_class = StandardPagination
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        seller = get_active_seller(self.request.user)
        return (
            services.sources_for(self.request.user, seller)
            .select_related("supplier", "category", "seller__user")
            .annotate(
                n_total=Count("items"),
                n_new=Count("items", filter=Q(items__status=SupplierItem.NEW)),
                n_linked=Count("items", filter=Q(items__status=SupplierItem.LINKED)),
                n_ignored=Count("items", filter=Q(items__status=SupplierItem.IGNORED)),
                n_missing=Count("items", filter=Q(items__missing=True)),
            )
            .order_by("name")
        )

    def perform_create(self, serializer):
        serializer.save(seller=_require_seller(self.request.user))

    def perform_destroy(self, instance):
        if instance.file:
            instance.file.delete(save=False)
        instance.delete()

    @action(detail=True, methods=["post"])
    def sync(self, request, pk=None):
        source = self.get_object()
        if source.runs.filter(status__in=ImportRun.ACTIVE).exists():
            raise ValidationError({"detail": _("Синхронизация уже выполняется")})
        run = ImportRun.objects.create(
            kind=ImportRun.KIND_SYNC, seller=source.seller, source=source, created_by=request.user
        )
        try:
            enqueue(sync_source_task, source.pk, run.pk)
        except QueueUnavailable:
            run.status, run.error = ImportRun.FAILED, QUEUE_DOWN
            run.save(update_fields=["status", "error"])
            return Response({"detail": QUEUE_DOWN}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        run.refresh_from_db()
        return Response(ImportRunSerializer(run).data, status=status.HTTP_202_ACCEPTED)

    @action(detail=True, methods=["get"])
    def runs(self, request, pk=None):
        source = self.get_object()
        return Response(ImportRunSerializer(source.runs.select_related("created_by")[:20], many=True).data)

    @action(detail=True, methods=["get"])
    def items(self, request, pk=None):
        source = self.get_object()
        qs = source.items.select_related("variant__product")
        p = request.query_params
        if p.get("status") in (SupplierItem.NEW, SupplierItem.LINKED, SupplierItem.IGNORED):
            qs = qs.filter(status=p["status"])
        if q := p.get("q", "").strip():
            qs = qs.filter(Q(name__icontains=q) | Q(sku__icontains=q) | Q(barcode__icontains=q))
        if "category" in p:
            qs = qs.filter(category_name=p["category"])
        if p.get("missing") == "1":
            qs = qs.filter(missing=True)
        if p.get("available") == "1":
            qs = qs.filter(Q(available=True) | Q(quantity__gt=0))
        page = self.paginate_queryset(qs.order_by("name", "id"))
        context = {**self.get_serializer_context(), "pricing": services.Pricing(source)}
        return self.get_paginated_response(SupplierItemSerializer(page, many=True, context=context).data)

    @action(detail=True, methods=["get"])
    def categories(self, request, pk=None):
        source = self.get_object()
        rows = (
            source.items.values("category_name")
            .annotate(total=Count("id"), new=Count("id", filter=Q(status=SupplierItem.NEW)))
            .order_by("category_name")
        )
        return Response(list(rows))

    @action(detail=True, methods=["post"])
    def link(self, request, pk=None):
        source = self.get_object()
        form = LinkSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        item = source.items.filter(pk=form.validated_data["item"]).first()
        if item is None:
            raise ValidationError({"item": _("Позиция не найдена")})
        try:
            services.link_item(item, form.validated_data["variant"])
        except services.ImportActionError as exc:
            raise ValidationError({"variant": str(exc)}) from None
        return Response({"ok": True})

    @action(detail=True, methods=["post"], url_path="items-status")
    def items_status(self, request, pk=None):
        source = self.get_object()
        form = ItemStatusSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        changed = services.set_status(source, form.validated_data["ids"], form.validated_data["status"])
        return Response({"changed": changed})

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        source = self.get_object()
        form = PublishSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        category = None
        if form.validated_data.get("category"):
            category = Category.objects.filter(pk=form.validated_data["category"]).first()
            if category is None:
                raise ValidationError({"category": _("Категория не найдена")})
        result = services.publish_items(
            source, form.validated_data["ids"], category=category, visible=form.validated_data.get("visible")
        )
        photos_queued = 0
        for variant_id, urls in result["created"]:
            if not urls:
                continue
            try:
                enqueue(download_photos_task, variant_id, urls)
                photos_queued += 1
            except QueueUnavailable:
                break
        return Response(
            {
                "created": len(result["created"]),
                "linked": result["linked"],
                "skipped": result["skipped"],
                "photos_queued": photos_queued,
            }
        )
