"""
Редактор товаров кабинета продавца (/api/manage/…): список, карточка, варианты, фото, показ на сайте.
Администратор видит все товары, продавец — только свои. Остатки здесь только для чтения:
они меняются движениями склада (приход, инвентаризация…).
"""

from decimal import Decimal
from io import BytesIO

from django.db import transaction
from django.db.models import Count, Exists, F, Min, OuterRef, ProtectedError, Q, Subquery, Sum
from django.db.models.functions import Coalesce
from django.utils.translation import gettext as _
from PIL import Image
from rest_framework import mixins, serializers, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from app.apps.storefronts.scope import depth
from app.apps.warehouse.permissions import IsWarehouseStaff, get_active_seller
from app.core.pagination import StandardPagination

from .models import Brand, Category, Product, ProductPhoto, ProductVariant
from .search import match_all
from .services import brand_by_name, discount_fields, editable_products

MAX_PHOTO_BYTES = 10 * 1024 * 1024
PHOTO_FORMATS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp"}
ORDERING = {"name": "name", "-name": "-name", "price": "price_min", "-price": "-price_min", "new": "-created", "updated": "-modified", "brand": "brand_name"}  # fmt: skip


def in_category(category_id) -> Q:
    """Категория вместе с подкатегориями (дерево — до 3 уровней): «Змішувачі» — и «для кухні», и «для ванни»."""
    return Q(category_id=category_id) | Q(category__parent_id=category_id) | Q(category__parent__parent_id=category_id)


class CanEditProduct(IsWarehouseStaff):
    """Кабинет: продавец или администратор; объект — только свой товар (администратор — любой)."""

    def has_object_permission(self, request, view, obj):
        product = obj if isinstance(obj, Product) else obj.product
        if request.user.is_superuser:
            return True
        seller = get_active_seller(request.user)
        return seller is not None and product.seller_id == seller.pk


# ---------------------------------------------------------------------------
# Сериализаторы
# ---------------------------------------------------------------------------


class VariantSerializer(serializers.ModelSerializer):
    old_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, allow_null=True, write_only=True
    )
    brand_name = serializers.CharField(required=False, allow_blank=True, max_length=255, write_only=True)
    brand = serializers.CharField(source="brand.name", read_only=True, default=None)
    original_price_value = serializers.SerializerMethodField()
    available_stock = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    photo = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            "id", "variant_name", "code", "barcode", "price", "old_price", "original_price_value", "discount",
            "cost_price", "available", "brand", "brand_name", "description", "stock", "reserved", "available_stock",
            "dimensions_width", "dimensions_height", "dimensions_depth", "dimensions_weight", "photo",
        ]  # fmt: skip
        read_only_fields = ["discount", "stock", "reserved"]
        extra_kwargs = {
            "price": {"required": True, "allow_null": False, "min_value": Decimal("0.01")},
            "code": {"required": False, "allow_null": True, "allow_blank": True, "validators": []},
            "barcode": {"required": False, "allow_null": True, "allow_blank": True, "validators": []},
            "cost_price": {"min_value": Decimal("0")},
        }

    def get_original_price_value(self, obj):
        return str(obj.original_price) if obj.discount and obj.original_price else None

    def get_photo(self, obj):
        return obj.photo.url if obj.photo else None

    def _unique(self, field, value):
        if not value:
            return None
        value = value.strip()
        qs = ProductVariant.objects.filter(**{f"{field}__iexact": value})
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise ValidationError({field: _("Уже есть у другого товара")})
        return value

    def validate(self, attrs):
        attrs["code"] = (
            self._unique("code", attrs.get("code")) if "code" in attrs else getattr(self.instance, "code", None)
        )
        if "barcode" in attrs:
            attrs["barcode"] = self._unique("barcode", attrs.get("barcode"))
        price = attrs.get("price", getattr(self.instance, "price", None))
        if "old_price" in attrs or "price" in attrs:
            current_old = self.instance.original_price if self.instance and self.instance.discount else None
            old = attrs.pop("old_price", current_old)
            if old is not None and price is not None and old <= price:
                raise ValidationError({"old_price": _("Старая цена должна быть больше цены")})
            attrs.update(discount_fields(Decimal(price).quantize(Decimal("0.01")), old))
        if "brand_name" in attrs:
            attrs["brand"] = brand_by_name(attrs.pop("brand_name"))
        return attrs

    def create(self, validated_data):
        variant = ProductVariant(**validated_data)
        variant.save()  # save(): код, штрихкод, slug, картинка штрихкода
        return variant

    def update(self, instance, validated_data):
        for key, value in validated_data.items():
            setattr(instance, key, value)
        if not instance.code:
            instance.code = instance.generate_unique_code()
        instance.save()
        return instance


class PhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = ProductPhoto
        fields = ["id", "url", "product_var"]

    def get_url(self, obj):
        return obj.photo.url if obj.photo else None


class ProductListSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    photo = serializers.SerializerMethodField()
    variants_count = serializers.IntegerField(read_only=True)
    price_min = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    stock = serializers.DecimalField(max_digits=12, decimal_places=3, read_only=True)
    visible = serializers.BooleanField(read_only=True)
    sku = serializers.CharField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "category_name", "photo", "variants_count", "price_min", "stock", "visible", "sku", "modified"]  # fmt: skip

    def get_photo(self, obj):
        return obj.photo.url if obj.photo else None


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    seller_name = serializers.CharField(source="seller.shop_name", read_only=True, default=None)
    photo = serializers.SerializerMethodField()
    photos = PhotoSerializer(many=True, read_only=True)
    variants = serializers.SerializerMethodField()
    # первый вариант при создании товара
    variant = VariantSerializer(write_only=True, required=False)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "category", "category_name", "description", "seller_name", "photo", "photos", "variants", "variant", "created", "modified"]  # fmt: skip
        read_only_fields = ["slug", "created", "modified"]
        extra_kwargs = {"name": {"required": True, "allow_blank": False, "max_length": 255}}

    def get_photo(self, obj):
        return obj.photo.url if obj.photo else None

    def get_variants(self, obj):
        return VariantSerializer(obj.variants.select_related("brand").order_by("id"), many=True).data

    def update(self, instance, validated_data):
        validated_data.pop("variant", None)  # варианты меняются отдельно (manage/variants/)
        return super().update(instance, validated_data)

    @transaction.atomic
    def create(self, validated_data):
        variant_data = validated_data.pop("variant", None)
        if not variant_data:
            raise ValidationError({"variant": _("Укажите цену товара")})
        product = Product.objects.create(**validated_data)
        variant_data.setdefault("variant_name", product.name)
        VariantSerializer().create({**variant_data, "product": product})
        return product


class BulkSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), allow_empty=False, max_length=500)
    action = serializers.ChoiceField(choices=["show", "hide", "category"])
    category = serializers.PrimaryKeyRelatedField(queryset=Category.objects.all(), required=False, allow_null=True)


# ---------------------------------------------------------------------------
# Представления
# ---------------------------------------------------------------------------


def _image(upload):
    if upload.size > MAX_PHOTO_BYTES:
        raise ValidationError({"photo": _("Фото больше 10 МБ")})
    try:
        content = upload.read()
        with Image.open(BytesIO(content)) as img:
            fmt = img.format
            img.verify()
    except Exception:  # noqa: BLE001 — Pillow бросает разные ошибки на битых файлах
        raise ValidationError({"photo": _("Файл не является изображением")}) from None
    if fmt not in PHOTO_FORMATS:
        raise ValidationError({"photo": _("Поддерживаются JPG, PNG и WebP")})
    upload.seek(0)
    return PHOTO_FORMATS[fmt]


class ManageProductViewSet(viewsets.ModelViewSet):
    permission_classes = [CanEditProduct]
    pagination_class = StandardPagination
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_serializer_class(self):
        return ProductListSerializer if self.action == "list" else ProductSerializer

    def get_queryset(self):
        user = self.request.user
        qs = editable_products(user, get_active_seller(user)).select_related("category", "seller")
        if self.action != "list":
            return qs.prefetch_related("photos")
        p = self.request.query_params
        visible = ProductVariant.objects.filter(product=OuterRef("pk"), available=True)
        qs = qs.annotate(
            variants_count=Count("variants", distinct=True),
            price_min=Min("variants__price"),
            stock=Coalesce(Sum(F("variants__stock") - F("variants__reserved")), Decimal(0)),
            visible=Exists(visible),
        )
        variants = ProductVariant.objects.filter(product=OuterRef("pk"))
        if q := p.get("q", "").strip():
            # Exists, а не JOIN по вариантам: иначе суммы остатков в аннотациях умножаются
            found = Exists(variants.filter(Q(code__icontains=q) | Q(barcode__icontains=q)))
            words = match_all(  # слова в любом порядке, окончания, по-русски, синонимы (search.py)
                q,
                lambda w: Q(name__icontains=w)
                | Exists(variants.filter(Q(variant_name__icontains=w) | Q(brand__name__icontains=w))),
            )
            qs = qs.filter(found | words if words is not None else found)
        if category := p.get("category"):
            qs = qs.filter(in_category(category)) if category != "none" else qs.filter(category__isnull=True)
        if brand := p.get("brand", "").strip():
            qs = qs.filter(Exists(variants.filter(brand__name__iexact=brand)))
        if p.get("visible") in ("1", "0"):
            qs = qs.filter(visible=p["visible"] == "1")
        if p.get("no_photo") == "1":
            qs = qs.filter(Q(photo="") | Q(photo__isnull=True))
        if p.get("in_stock") == "1":
            qs = qs.filter(stock__gt=0)
        sku = ProductVariant.objects.filter(product=OuterRef("pk")).order_by("id").values("code")[:1]
        brand_name = variants.exclude(brand__isnull=True).order_by("id").values("brand__name")[:1]
        return qs.annotate(sku=Subquery(sku), brand_name=Subquery(brand_name)).order_by(
            ORDERING.get(p.get("ordering"), "-modified"), "-id"
        )

    @action(detail=False, methods=["get"])
    def facets(self, request):
        """Для фильтров кабинета: разделы и категории с числом товаров (с подкатегориями) и бренды продавца."""
        user = request.user
        products = editable_products(user, get_active_seller(user))
        direct = dict(products.values_list("category_id").annotate(n=Count("id")).exclude(category_id=None))
        parents = dict(Category.objects.values_list("id", "parent_id"))
        totals: dict[int, int] = {}
        for category_id, n in direct.items():
            node, hops = category_id, 0
            while node and hops < 4:  # товар считается и в разделе, и в направлении выше
                totals[node] = totals.get(node, 0) + n
                node, hops = parents.get(node), hops + 1
        categories = [
            {"id": c.pk, "name": c.name, "count": totals[c.pk], "depth": depth(c)}
            for c in Category.objects.filter(pk__in=totals).select_related("parent__parent")
        ]
        brands = (
            ProductVariant.objects.filter(product__in=products, brand__isnull=False)
            .exclude(brand__name="")
            .values("brand__name")
            .annotate(n=Count("product", distinct=True))
            .order_by("-n", "brand__name")
        )
        return Response(
            {
                "categories": sorted(categories, key=lambda c: (c["depth"], -c["count"], c["name"])),
                "brands": [{"name": b["brand__name"], "count": b["n"]} for b in brands],
            }
        )

    def perform_create(self, serializer):
        user = self.request.user
        seller = get_active_seller(user)
        if seller is None and not user.is_superuser:
            raise ValidationError({"detail": _("Создавать товары может только одобренный продавец")})
        product = serializer.save(seller=seller)
        if product.variants.filter(available=True).exists():
            _announce([product.pk])

    def destroy(self, request, *args, **kwargs):
        product = self.get_object()
        try:
            with transaction.atomic():
                product.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": _("Товар есть в заказах или в журнале склада — его можно только скрыть с сайта")}
            ) from None
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def variants(self, request, pk=None):
        product = self.get_object()
        serializer = VariantSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(product=product)
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def photos(self, request, pk=None):
        """Загрузить фото: первое становится главным, остальные — в галерею (можно привязать к варианту)."""
        product = self.get_object()
        files = request.FILES.getlist("photo")
        if not files:
            raise ValidationError({"photo": _("Выберите фото")})
        variant_id = request.data.get("variant") or None
        if variant_id and not product.variants.filter(pk=variant_id).exists():
            raise ValidationError({"variant": _("Вариант не найден")})
        for upload in files[:20]:
            ext = _image(upload)
            name = f"{product.slug or product.pk}.{ext}"
            if not product.photo:
                product.photo.save(name, upload, save=True)
            else:
                ProductPhoto.objects.create(product=product, product_var_id=variant_id, photo=upload)
        product.refresh_from_db()
        return Response(ProductSerializer(product).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path=r"photos/(?P<photo_id>main|\d+)/(?P<op>delete|main)")
    def photo_op(self, request, pk=None, photo_id=None, op=None):
        """photos/main/delete — убрать главное фото; photos/<id>/delete; photos/<id>/main — сделать главным."""
        product = self.get_object()
        if photo_id == "main":
            # файлы с диска не удаляем: в старых данных один файл бывает у нескольких записей
            if op == "delete" and product.photo:
                product.photo = None
                # главным становится первое фото галереи
                first = product.photos.order_by("id").first()
                if first:
                    product.photo.name, first.photo.name = first.photo.name, ""
                    first.delete()
                product.save()
        else:
            photo = product.photos.filter(pk=photo_id).first()
            if photo is None:
                raise ValidationError({"photo": _("Фото не найдено")})
            if op == "delete":
                photo.delete()
            else:
                old_main = product.photo.name if product.photo else ""
                product.photo.name = photo.photo.name
                product.save()
                if old_main:
                    photo.photo.name = old_main
                    photo.save()
                else:
                    photo.delete()
        product.refresh_from_db()
        return Response(ProductSerializer(product).data)

    @action(detail=False, methods=["post"])
    def bulk(self, request):
        form = BulkSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        products = self.get_queryset().filter(pk__in=form.validated_data["ids"])
        kind = form.validated_data["action"]
        if kind == "category":
            changed = products.update(category=form.validated_data.get("category"))
        else:
            changed = ProductVariant.objects.filter(product__in=products).update(available=kind == "show")
            if kind == "show":
                _announce(list(products.values_list("pk", flat=True)))
        return Response({"changed": changed})


class ManageVariantViewSet(mixins.UpdateModelMixin, mixins.DestroyModelMixin, viewsets.GenericViewSet):
    serializer_class = VariantSerializer
    permission_classes = [CanEditProduct]

    def get_queryset(self):
        user = self.request.user
        return ProductVariant.objects.filter(
            product__in=editable_products(user, get_active_seller(user))
        ).select_related("product", "brand")

    def perform_update(self, serializer):
        was_visible = serializer.instance.available
        variant = serializer.save()
        if variant.available and not was_visible:
            _announce([variant.product_id])

    def destroy(self, request, *args, **kwargs):
        variant = self.get_object()
        if variant.product.variants.count() == 1:
            raise ValidationError({"detail": _("Это единственный вариант — удалите товар целиком или скройте его")})
        try:
            with transaction.atomic():
                variant.delete()
        except ProtectedError:
            raise ValidationError(
                {"detail": _("Вариант есть в заказах или в журнале склада — его можно только скрыть с сайта")}
            ) from None
        return Response(status=status.HTTP_204_NO_CONTENT)


class ManageBrandsView(viewsets.ViewSet):
    permission_classes = [IsWarehouseStaff]

    def list(self, request):
        names = (
            Brand.objects.exclude(name__isnull=True).exclude(name="").order_by("name").values_list("name", flat=True)
        )
        return Response(sorted(set(names), key=str.lower))


def _announce(product_ids):
    """Автопубликация новинок в Telegram (если включена в настройках магазина)."""
    from app.apps.marketing.services import announce

    announce(product_ids)
