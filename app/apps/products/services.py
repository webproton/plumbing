"""Общая логика товаров: права на редактирование, цена со «старой ценой», бренды."""

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Q

from .models import Brand, Product, ProductVariant


def discount_fields(price: Decimal, old: Decimal | None) -> dict:
    """Поля варианта для цены со «старой ценой» (как их ожидает ProductVariant.save)."""
    if old and old > price:
        discount = int(((Decimal(1) - price / old) * 100).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        if discount >= 1:
            return {"price": price, "original_price": old, "discount": min(discount, 99)}
    return {"price": price, "original_price": None, "discount": 0}


def editable_variants(seller):
    """Для импорта: свои товары продавца; у администратора — ещё и общие товары магазина (без продавца)."""
    cond = Q(product__seller=seller)
    if seller.user.is_superuser:
        cond |= Q(product__seller__isnull=True)
    return ProductVariant.objects.filter(cond)


def editable_products(user, seller):
    """Для редактора в кабинете: администратор — все товары, продавец — только свои."""
    if user.is_superuser:
        return Product.objects.all()
    return Product.objects.filter(seller=seller) if seller else Product.objects.none()


def brand_by_name(name: str):
    name = (name or "").strip()[:255]
    if not name:
        return None
    return Brand.objects.filter(name__iexact=name).first() or Brand.objects.create(name=name)
