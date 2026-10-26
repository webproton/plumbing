from django.contrib import admin
from django.core.cache import cache

from .models import Storefront
from .resolve import DOMAINS_CACHE_KEY


@admin.register(Storefront)
class StorefrontAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "verticals", "domains", "is_demo", "is_active", "sort_order")
    list_editable = ("is_demo", "is_active", "sort_order")
    search_fields = ("name", "slug", "domains")
    filter_horizontal = ("sellers",)
    prepopulated_fields = {"slug": ("name",)}
    fieldsets = (
        (None, {"fields": ("name", "slug", "tagline", "tagline_ru", "is_active", "is_demo", "sort_order")}),
        ("Что показывать", {"fields": ("verticals", "sellers")}),
        (
            "Адрес сайта",
            {"fields": ("domains",), "description": "Без домена витрина открывается по ссылке /?store=<slug>"},
        ),
        ("Оформление и контакты", {"fields": ("brand_color", "logo", "phone", "email", "address", "telegram_bot")}),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        cache.delete(DOMAINS_CACHE_KEY)  # новый домен — сразу
