from django.contrib import admin

from app.apps.products.models import ProductVariant

from .models import Seller, Shop


# === Shop Inline для Seller ===
class ShopInline(admin.StackedInline):  # можно TabularInline, если хочется компактнее
    model = Shop
    extra = 0
    fields = ("description", "logo", "banner", "active", "address")
    readonly_fields = ()  # можно добавить 'logo' если только просмотр


# === Seller Admin ===
@admin.register(Seller)
class SellerAdmin(admin.ModelAdmin):
    list_display = (
        "shop_name",
        "user",
        "is_approved",
        "commission_percent",
        "verified",
        "created_at",
        "edrpou",
        "has_shop",
        "shop_active",
        "warehouses_count",
        "products_count",
    )
    list_filter = ("is_approved", "verified")
    search_fields = ("shop_name", "user__email", "edrpou", "bank_account")
    ordering = ("-created_at",)
    inlines = [ShopInline]  # подключаем магазин как инлайн

    # Вычисляемое поле: есть ли магазин
    def has_shop(self, obj):
        return hasattr(obj, "shop")

    has_shop.boolean = True
    has_shop.short_description = "Магазин есть"

    # Вычисляемое поле: активен ли магазин
    def shop_active(self, obj):
        if hasattr(obj, "shop"):
            return obj.shop.active
        return False

    shop_active.boolean = True
    shop_active.short_description = "Магазин активен"

    # Вычисляемое поле: количество складов
    def warehouses_count(self, obj):
        return obj.warehouses.count()  # через related_name в Warehouse

    warehouses_count.short_description = "Складов"

    # Вычисляемое поле: количество товаров
    def products_count(self, obj):
        return ProductVariant.objects.filter(product__seller=obj).count()

    products_count.short_description = "Товаров"


# === Shop Admin (отдельно, если нужен) ===
@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    list_display = ("seller", "active", "address")
    list_filter = ("active",)
    search_fields = ("seller__shop_name", "address")
