from django.db import transaction
from django.db.models import Min, Prefetch
from django.utils.translation import gettext as _
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

from .filters import ProductFilters
from .models import Category, Product, ProductVariant, Wishlist
from .serializers import (
    CategorySerializer,
    ProductDetailSerializer,
    ProductListSerializer,
    WishlistSerializer,
)

# Связанные объекты варианта, которые отдаёт ProductVariantSerializer (без них — десятки запросов на карточку)
VARIANT_FK = (
    "product",
    "brand",
    "ball",
    "material",
    "manufacturer",
    "thread_size",
    "type_of_product",
    "product_thread",
    "color",
    "body_material",
    "pattern",
    "bed_type",
    "filling",
    "armrests",
    "mattress_base",
    "mechanism",
    "bed_type_form",
)
VARIANT_M2M = ("included_items", "upholstery_materials", "color_options")

ORDERING = {
    "price": "min_price",
    "-price": "-min_price",
    "name": "name",
    "-name": "-name",
    "new": "-created",
}


def visible_variants():
    return ProductVariant.objects.filter(available=True).select_related(*VARIANT_FK).prefetch_related(*VARIANT_M2M)


def catalog_queryset():
    """Товары, у которых есть хотя бы один видимый вариант, с минимальной ценой видимых вариантов."""
    return (
        Product.objects.filter(variants__available=True)
        .annotate(min_price=Min("variants__price"))
        .select_related("category")
        .prefetch_related(Prefetch("variants", queryset=visible_variants().order_by("id"), to_attr="visible_variants"))
    )


class ProductPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100


class NewProducts(viewsets.GenericViewSet, mixins.ListModelMixin):
    serializer_class = ProductListSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        return catalog_queryset().order_by("-id")[:6]


class CategoryList(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"
    queryset = Category.objects.order_by("name")


class ProductListView(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """
    Каталог. Параметры: фильтры ProductFilters (category, search, min_price, …),
    ordering = price | -price | name | -name | new, page, page_size.
    """

    filterset_class = ProductFilters
    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]
    pagination_class = ProductPagination

    def get_queryset(self):
        qs = catalog_queryset()
        if self.action == "retrieve":
            return qs.prefetch_related("photos")
        ordering = ORDERING.get(self.request.query_params.get("ordering", ""), "min_price")
        return qs.order_by(ordering, "id")

    def get_serializer_class(self):
        return ProductDetailSerializer if self.action == "retrieve" else ProductListSerializer


class WishlistViewSet(
    mixins.CreateModelMixin, mixins.ListModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet
):
    """Избранное авторизованного пользователя (у гостя оно хранится в localStorage)."""

    serializer_class = WishlistSerializer

    def get_permissions(self):
        if self.action == "list":
            return [permissions.AllowAny()]  # гость получает пустой список
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        if not self.request.user.is_authenticated:
            return Wishlist.objects.none()
        return (
            Wishlist.objects.filter(user=self.request.user)
            .select_related("product_variant__product")
            .order_by("-added_at")
        )

    def _respond_list(self):
        return Response(self.get_serializer(self.get_queryset(), many=True).data)

    def create(self, request, *args, **kwargs):
        variant_id = request.data.get("product_variant_id")
        if not variant_id:
            return Response({"detail": "product_variant_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        variant = ProductVariant.objects.filter(pk=variant_id).first()
        if variant is None:
            return Response({"detail": "Product variant not found"}, status=status.HTTP_404_NOT_FOUND)
        item, created = Wishlist.objects.get_or_create(user=request.user, product_variant=variant)
        return Response(
            self.get_serializer(item).data, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
        )

    def _variant_ids(self, raw):
        ids = []
        for value in raw if isinstance(raw, list) else []:
            if isinstance(value, dict):
                value = value.get("product_variant_id")
            try:
                ids.append(int(value))
            except (TypeError, ValueError):
                continue
        return set(ProductVariant.objects.filter(pk__in=ids).values_list("pk", flat=True))

    @action(detail=False, methods=["put"], url_path="bulk-update")
    def bulk_update(self, request):
        """Заменить избранное переданным списком [{product_variant_id}, …]."""
        if not isinstance(request.data, list):
            return Response({"detail": "Data should be a list of items."}, status=status.HTTP_400_BAD_REQUEST)
        ids = self._variant_ids(request.data)
        with transaction.atomic():
            Wishlist.objects.filter(user=request.user).exclude(product_variant_id__in=ids).delete()
            Wishlist.objects.bulk_create(
                [Wishlist(user=request.user, product_variant_id=i) for i in ids], ignore_conflicts=True
            )
        return self._respond_list()

    @action(detail=False, methods=["post"], url_path="clear")
    def clear_wishlist(self, request):
        deleted, _details = Wishlist.objects.filter(user=request.user).delete()
        return Response({"detail": _("Удалено {deleted} элементов избранного").format(deleted=deleted)})

    @action(detail=False, methods=["post"], url_path="merge")
    def merge_wishlist(self, request):
        """Добавить к избранному гостевые позиции после входа: {variant_ids: [...]}."""
        ids = self._variant_ids(request.data.get("variant_ids"))
        if not ids:
            return Response({"detail": _("Требуется список variant_ids")}, status=status.HTTP_400_BAD_REQUEST)
        Wishlist.objects.bulk_create(
            [Wishlist(user=request.user, product_variant_id=i) for i in ids], ignore_conflicts=True
        )
        return self._respond_list()
