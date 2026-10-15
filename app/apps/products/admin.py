import logging

from django.contrib import admin
from django.http import JsonResponse
from django.urls import path
from django.utils.html import format_html

from .actions import apply_discount_to_variants
from .models import (
    Ball,
    Brand,
    Category,
    ColorProduct,
    Manufacturer,
    MaterialProduct,
    Product,
    ProductPhoto,
    ProductThread,
    ProductVariant,
    Thread,
    TypeOfProduct,
    Wishlist,
)
from .utils.banner_generator import generate_banner
from .utils.color_utils import rgb_to_basic_color

logger = logging.getLogger(__name__)


def generate_banners(modeladmin, request, queryset):
    count = 0
    for product in queryset:
        generate_banner(product)
        count += 1
    modeladmin.message_user(request, f"Баннеры сгенерированы для {count} продуктов.")


generate_banners.short_description = "Сгенерировать баннеры для выбранных продуктов"


class ManufacturerAdmin(admin.ModelAdmin):
    "Manufacturer"

    list_display = ["brand_name", "country", "id"]


class ProductThreadAdmin(admin.ModelAdmin):
    "тип різьби В ВН .... і id"

    list_display = ["thread_type", "id"]


class MaterialProductAdmin(admin.ModelAdmin):
    "зчого виготовлений ..."

    list_display = ["name", "id"]


class ThreadAdmin(admin.ModelAdmin):
    "size thread"

    list_display = ["inches", "id"]


class BallProductAdmin(admin.ModelAdmin):
    "size thread"

    list_display = ["ball_material_type", "id"]


class ProductAdmin(admin.ModelAdmin):
    "product"

    list_display = [
        "name",
        "id",
        "category",
    ]
    search_fields = ["name", "id"]
    list_filter = ("category",)
    actions = [generate_banners]


class ProductVariantAdmin(admin.ModelAdmin):
    """Product Variant Admin with search functionality for Product field"""

    # Остатки меняются только складскими операциями (журнал движений), не руками.
    readonly_fields = ["stock", "reserved"]
    autocomplete_fields = ["product"]
    list_editable = ("color",)
    list_display = [
        "code",
        "product",
        "photo_preview",
        "color",
        "product_id",
        "id",
        "discount",
        "price",
        "original_price",
    ]
    search_fields = [
        "code",
        "product__name",
        "variant_name",
        "color__name",
        "product__id",
    ]  # добавляем поиск по коду и имени продукта
    list_filter = ("product__category",)  # фильтр по категории продукта
    actions = [apply_discount_to_variants]  # если хочешь применять скидку на уровне вариантов

    def photo_preview(self, obj):
        """Мини-превью первой фотки варианта"""
        photo = obj.photos_variant.first()
        if photo and photo.photo:
            return format_html(
                '<img src="{}" class="pipette-image" '
                'style="max-height: 50px; cursor: crosshair;" '
                'data-variant-id="{}"/>',
                photo.photo.url,
                obj.id,
            )
        return "—"

    photo_preview.short_description = "Фото"
    photo_preview.allow_tags = True

    class Media:
        js = ("js/pipette.js",)  # подключаем свой скрипт

    # ✅ endpoint для AJAX
    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                "detect-color/",
                self.admin_site.admin_view(self.detect_color),
                name="detect-color",
            ),
        ]
        return custom_urls + urls

    def detect_color(self, request):
        try:
            r = int(request.GET.get("r"))
            g = int(request.GET.get("g"))
            b = int(request.GET.get("b"))
            variant_id = int(request.GET.get("variant"))

            # определяем название цвета
            color_name = rgb_to_basic_color((r, g, b))

            # ищем или создаём ColorProduct
            from app.apps.products.models import ColorProduct

            color_obj = ColorProduct.objects.filter(name=color_name).first()
            if not color_obj:
                color_obj = ColorProduct.objects.create(name=color_name)

            # обновляем Variant
            variant = ProductVariant.objects.filter(id=variant_id).first()
            if variant:
                variant.color = color_obj
                variant.save(update_fields=["color"])

            return JsonResponse({"color": color_name})

        except Exception as e:
            return JsonResponse({"error": str(e)}, status=400)


class WishlistAdmin(admin.ModelAdmin):
    list_display = ["user", "id", "product_variant"]


class CategoryAdmin(admin.ModelAdmin):
    list_display = ["id", "name", "slug"]


@admin.register(ProductPhoto)
class ProductPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "product_name", "variant_code", "photo_preview")
    search_fields = ("id", "product__name", "product_var__code")

    autocomplete_fields = ["product", "product_var"]  # 🔑

    def product_name(self, obj):
        return obj.product.name if obj.product else "—"

    product_name.short_description = "Продукт"

    def variant_code(self, obj):
        return obj.product_var.code if obj.product_var else "—"

    variant_code.short_description = "Код варианта"

    def photo_preview(self, obj):
        if obj.photo:
            return format_html(
                '<div style="text-align:center;">'
                '<img src="{}" width="80" height="60" style="object-fit:cover; display:block; margin:auto;"/>'
                "<br><small>ID: {}</small>"
                "</div>",
                obj.photo.url,
                obj.id,
            )
        return "—"

    photo_preview.short_description = "Превью"


admin.site.register(Product, ProductAdmin)
admin.site.register(ProductThread, ProductThreadAdmin)
admin.site.register(MaterialProduct, MaterialProductAdmin)
admin.site.register(Ball, BallProductAdmin)

admin.site.register(Thread, ThreadAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(Brand)
admin.site.register(Manufacturer, ManufacturerAdmin)
admin.site.register(TypeOfProduct)
admin.site.register(ColorProduct)
admin.site.register(ProductVariant, ProductVariantAdmin)
admin.site.register(Wishlist, WishlistAdmin)
