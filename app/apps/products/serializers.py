from rest_framework import serializers
from .models import (Product, Category, Brand,
                      ProductThread, Thread, Manufacturer,
                        MaterialProduct, ProductPhoto, 
                        ColorProduct, ProductVariant, Wishlist,
                        IncludedItem,BodyMaterial,Pattern,
                        BedType,Filling,Armrest,UpholsteryMaterial,
                        Mechanism,MattressBase,ColorOption,TypeOfProduct,Form
                        
                        )
from django.urls import reverse
from django.conf import settings
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response


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
    """Product color multiple serilizer """

    class Meta:
        model = ColorProduct
        fields = ["id", "name"]


class ProductPhotoSerializer(serializers.ModelSerializer):
    """Product Photos multiple serilizer """

    class Meta:
        model = ProductPhoto
        fields = ["id", "product", "photo"]


class ThreadSerializer(serializers.ModelSerializer):
    """Serializer for Thread model."""

    class Meta:
        model = Thread
        fields = ['inches', 'id']


class ProductThreadSerializer(serializers.ModelSerializer):
    """Serializer for ProductThread model."""

    class Meta:
        model = ProductThread
        fields = ['thread_type', 'id']


class BrandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Brand
        fields = ["name", "id"]


class ManufacturerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Manufacturer
        fields = ["brand_name", "country", "id"]


class CategorySerializer(serializers.ModelSerializer):
    """category list serializer its links to list products this categories"""

    # products = serializers.SerializerMethodField()
    product_list = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ["id","slug", "name", "product_list", "photo"]

    def get_product_list(self, category):
        # Generate the URL for the filtered product list for the category
        # request = self.context.get('request')
        return reverse('apps.products:product-list') + f'?category={category.id}'

    def get_products(self, category):
        products = category.products.all()
        request = self.context.get('request')
        links = {}
        for product in products:
            url = reverse('products:product-list')
            links[product.name] = request.build_absolute_uri(url)
        return links


class MaterialProductSerializer(serializers.ModelSerializer):
    """ material of products"""
    class Meta:
        model = MaterialProduct
        fields = ["id", "name"]


class BallSerializer(serializers.ModelSerializer):
    """ material of products"""
    ball_material_type = MaterialProductSerializer(read_only=True)

    class Meta:
        model = MaterialProduct
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
    
    class Meta:
        model = ProductVariant
        fields = [
            "id","slug","product","productSlug","discount","original_price", "code","variantSlug", "product_name", "price", "brand","thread_size",
            "product_thread", "manufacturer",
            "material", "ball", "dimensions_width",
            "dimensions_height","dimensions_weight", 
            "dimensions_thickness", "type_of_product",
            "color", "available","photo","description","banner_url",
            "included_items","body_material","pattern","bed_type","filling",
            "seat_depth","armrests","storage_niche","upholstery_materials","mattress_base",
            "mechanism","color_options","features","custom_size_available","bed_length",
            "bed_width","sleeping_places","dimensions_depth","seat_height","bed_type_form"


            ]
        
    def get_photo(self, obj):
        if obj.photo:
            return obj.photo.url
        # fallback: если фото нет у варианта, взять фото из продукта
        return obj.product.photo.url if obj.product.photo else None
    

    def get_banner_url(self, obj):
        return f"/media/banners/{obj.id}_banner.png"

class ProductDetailSerializer(serializers.ModelSerializer):
    variants = ProductVariantSerializer(read_only=True, many=True)
    photos = ProductPhotoSerializer(read_only=True, many=True)
    category = CategorySerializer(read_only=True) 

    # thread_size = ThreadSerializer(read_only=True, many=True)
    # product_thread = ProductThreadSerializer(read_only=True, many=True)

    

    class Meta:
        model = Product
        fields = ["id", "slug", "name", "category", "photo","photos", "variants", 'description']


class ProductListSerializer(serializers.ModelSerializer):
    """products 
    """
    category = serializers.CharField(source="category.name", read_only=True)
    category_id = serializers.IntegerField(source="category.id", read_only=True)  # <--- Добавь это!
    photo = serializers.SerializerMethodField(method_name="get_photo")
    first_variant = serializers.SerializerMethodField()
    price = serializers.SerializerMethodField()
    banner_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Product
        fields = ["id","slug", "name",  "category","category_id", "price", "photo","banner_url", "first_variant",]

    @staticmethod
    def get_photo(product):
        return getattr(product.photo, 'url', '')
    
    def get_banner_url(self, obj):
        return f"/media/banners/{obj.id}_banner.png"
    
    def get_first_variant(self, product):
        # This assumes `product` already contains prefetched/filtered variants in your view
        # метод щоб отримати продукти 
        # отримуємо  продукти  із запиту  і віддаємо з заданними параметрами 
        filtered_variants = getattr(product, 'filtered_variants', [])
        
        if filtered_variants:
            first_variant = filtered_variants[0]
        else:
            first_variant = product.variants.first()

        if first_variant:
            return ProductVariantSerializer(first_variant).data
        return None
        
    @staticmethod
    def get_photo(product):
        if product.photo:
            return product.photo.url
        return None
    
    def get_price(self, product):
        first_variant = product.variants.first()
        if first_variant:
            return first_variant.price
        return None   


class CategoryDetailSerializer(serializers.ModelSerializer):
    list_of_products = ProductListSerializer(many=True, source="products", read_only=True)

    class Meta:
        model = Category
        fields = ["list_of_products"]


class ProductSetLikesSerializer(serializers.ModelSerializer):

    class Meta:
        model = Product
        fields = ["like_user"]

class WishlistSerializer(serializers.ModelSerializer):

    # Для вывода (подробности варианта продукта)

    product_variant = ProductVariantSerializer(read_only=True)

    productSlug = serializers.CharField(source="product.slug", read_only=True)
    variantSlug = serializers.CharField(source="slug", read_only=True)
    
    # Для создания — поле для ввода ID варианта
    product_variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.all(),
        write_only=True,
        source='product_variant'  # Связываем с полем модели
    )

    # product_variant_slug = serializers.SlugRelatedField(
    # queryset=ProductVariant.objects.all(),
    # write_only=True,
    # slug_field="slug",
    # source="product_variant"
    # )
    
    product_variant_slug = serializers.SlugRelatedField(
    queryset=ProductVariant.objects.none(),
    write_only=True,
    slug_field="slug",
    source="product_variant"
)

    class Meta:
        model = Wishlist
        fields = ["id", "product_variant", "productSlug", "variantSlug" , "product_variant_id", "product_variant_slug", "added_at"]


    def validate_product_variant(self, value):

        user = self.context['request'].user
        if not user.is_authenticated:
            raise serializers.ValidationError("Только авторизованные пользователи могут добавлять в избранное.")
        # Убираем проверку на существование, так как toggle обрабатывается в view
        return value 
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        product = self.context.get('product')  # передаем через context
        if product:
            self.fields['product_variant_slug'].queryset = ProductVariant.objects.filter(product=product)




