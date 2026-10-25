from django.db.models import Min
from django.urls import reverse
from rest_framework import serializers

from .models import (
    Armrest,
    Ball,
    BedType,
    BodyMaterial,
    Brand,
    Category,
    ColorOption,
    ColorProduct,
    Filling,
    Form,
    IncludedItem,
    Manufacturer,
    MaterialProduct,
    MattressBase,
    Mechanism,
    Pattern,
    Product,
    ProductPhoto,
    ProductThread,
    ProductVariant,
    Thread,
    TypeOfProduct,
    UpholsteryMaterial,
    Wishlist,
)

# --- простые сериализаторы для связанных моделей ---


class FormSerializer(serializers.ModelSerializer):
    class Meta:
        model = Form
        fields = ["id", "name"]


class TypeOfProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = TypeOfProduct
        fields = ["id", "name"]


class IncludedItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = IncludedItem
        fields = ["id", "name"]


class BodyMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = BodyMaterial
        fields = ["id", "name"]


class PatternSerializer(serializers.ModelSerializer):
    class Meta:
        model = Pattern
        fields = ["id", "name"]


class BedTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BedType
        fields = ["id", "name"]


class FillingSerializer(serializers.ModelSerializer):
    class Meta:
        model = Filling
        fields = ["id", "name"]


class ArmrestSerializer(serializers.ModelSerializer):
    class Meta:
        model = Armrest
        fields = ["id", "name"]


class UpholsteryMaterialSerializer(serializers.ModelSerializer):
    class Meta:
        model = UpholsteryMaterial
        fields = ["id", "name"]


class MattressBaseSerializer(serializers.ModelSerializer):
    class Meta:
        model = MattressBase
        fields = ["id", "name"]


class MechanismSerializer(serializers.ModelSerializer):
    class Meta:
        model = Mechanism
        fields = ["id", "name"]


class ColorOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ColorOption
        fields = ["id", "name"]


class ColorSerializer(serializers.ModelSerializer):
    """Product color multiple serilizer"""

    class Meta:
        model = ColorProduct
        fields = ["id", "name"]


class ProductPhotoSerializer(serializers.ModelSerializer):
    """Product Photos multiple serilizer"""

    class Meta:
        model = ProductPhoto
        fields = ["id", "product", "photo"]


class ThreadSerializer(serializers.ModelSerializer):
    """Serializer for Thread model."""

    class Meta:
        model = Thread
        fields = ["inches", "id"]


class ProductThreadSerializer(serializers.ModelSerializer):
    """Serializer for ProductThread model."""

    class Meta:
        model = ProductThread
        fields = ["thread_type", "id"]


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["name", "id"]


class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = ["brand_name", "country", "id"]


class CategorySerializer(serializers.ModelSerializer):
    """Категория + ссылка на отфильтрованный каталог."""

    product_list = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id", "slug", "name", "product_list", "photo"]

    def get_product_list(self, category):
        return reverse("products:product-list") + f"?category={category.slug}"


class MaterialProductSerializer(serializers.ModelSerializer):
    """material of products"""

    class Meta:
        model = MaterialProduct
        fields = ["id", "name"]


class BallSerializer(serializers.ModelSerializer):
    ball_material_type = MaterialProductSerializer(read_only=True)

    class Meta:
        model = Ball
        fields = ["id", "ball_material_type"]


class ProductSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["id", "slug", "name"]


class ProductVariantSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)  # вместо просто ID

    productSlug = serializers.CharField(source="product.slug", read_only=True)
    variantSlug = serializers.CharField(source="slug", read_only=True)

    brand = BrandSerializer(read_only=True)
    ball = BallSerializer(read_only=True)
    material = MaterialProductSerializer(read_only=True)
    manufacturer = ManufacturerSerializer(read_only=True)
    thread_size = ThreadSerializer(read_only=True)
    type_of_product = TypeOfProductSerializer(read_only=True)
    product_thread = ProductThreadSerializer(read_only=True)
    color = ColorSerializer(read_only=True)
    product_name = serializers.CharField(source="product.name", read_only=True)
    photo = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()

    included_items = IncludedItemSerializer(many=True, read_only=True)
    body_material = BodyMaterialSerializer(read_only=True)
    pattern = PatternSerializer(read_only=True)
    bed_type = BedTypeSerializer(read_only=True)
    filling = FillingSerializer(read_only=True)
    armrests = ArmrestSerializer(read_only=True)
    upholstery_materials = UpholsteryMaterialSerializer(many=True, read_only=True)
    mattress_base = MattressBaseSerializer(read_only=True)
    mechanism = MechanismSerializer(read_only=True)
    color_options = ColorOptionSerializer(many=True, read_only=True)
    bed_type_form = FormSerializer(read_only=True)
    in_stock = serializers.SerializerMethodField(help_text="Есть ли товар в наличии (остаток минус резерв > 0)")
    available_qty = serializers.DecimalField(source="available_stock", max_digits=12, decimal_places=3, read_only=True)

    class Meta:
        model = ProductVariant
        fields = [
            "id",
            "slug",
            "product",
            "productSlug",
            "discount",
            "original_price",
            "code",
            "variantSlug",
            "product_name",
            "price",
            "brand",
            "thread_size",
            "product_thread",
            "manufacturer",
            "material",
            "ball",
            "dimensions_width",
            "dimensions_height",
            "dimensions_weight",
            "dimensions_thickness",
            "type_of_product",
            "color",
            "available",
            "photo",
            "description",
            "banner_url",
            "included_items",
            "body_material",
            "pattern",
            "bed_type",
            "filling",
            "seat_depth",
            "armrests",
            "storage_niche",
            "upholstery_materials",
            "mattress_base",
            "mechanism",
            "color_options",
            "features",
            "attributes",
            "custom_size_available",
            "bed_length",
            "bed_width",
            "sleeping_places",
            "dimensions_depth",
            "seat_height",
            "bed_type_form",
            "in_stock",
            "available_qty",
        ]

    def get_in_stock(self, obj):
        return obj.available_stock > 0

    def get_photo(self, obj):
        if obj.photo:
            return obj.photo.url
        # fallback: если фото нет у варианта, взять фото из продукта
        return obj.product.photo.url if obj.product.photo else None

    def get_banner_url(self, obj):
        return f"/media/banners/{obj.id}_banner.png"


class ProductDetailSerializer(serializers.ModelSerializer):
    # только видимые варианты (Prefetch to_attr="visible_variants" во view)
    variants = ProductVariantSerializer(source="visible_variants", read_only=True, many=True)
    photos = ProductPhotoSerializer(read_only=True, many=True)
    category = CategorySerializer(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "slug", "name", "category", "photo", "photos", "variants", "description"]


class ProductListSerializer(serializers.ModelSerializer):
    """products"""

    category = serializers.CharField(source="category.name", read_only=True)
    category_id = serializers.IntegerField(source="category.id", read_only=True)
    photo = serializers.SerializerMethodField()
    first_variant = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "slug",
            "name",
            "category",
            "category_id",
            "price",
            "photo",
            "banner_url",
            "first_variant",
        ]

    def get_banner_url(self, obj):
        return f"/media/banners/{obj.id}_banner.png"

    def get_first_variant(self, product):
        variants = getattr(product, "visible_variants", None)
        if variants is None:
            variants = list(product.variants.filter(available=True).order_by("id")[:1])
        return ProductVariantSerializer(variants[0]).data if variants else None

    def get_photo(self, product):
        return product.photo.url if product.photo else None

    def get_price(self, product):
        """Минимальная цена среди видимых вариантов («от …»)."""
        if hasattr(product, "min_price"):
            return product.min_price
        return product.variants.filter(available=True).aggregate(p=Min("price"))["p"]


class CategoryDetailSerializer(serializers.ModelSerializer):
    list_of_products = ProductListSerializer(many=True, source="products", read_only=True)

    class Meta:
        model = Category
        fields = ["list_of_products"]


class WishlistSerializer(serializers.ModelSerializer):
    product_variant = ProductVariantSerializer(read_only=True)
    productSlug = serializers.CharField(source="product_variant.product.slug", read_only=True)
    variantSlug = serializers.CharField(source="product_variant.slug", read_only=True)

    class Meta:
        model = Wishlist
        fields = ["id", "product_variant", "productSlug", "variantSlug", "added_at"]
