"""Каталог в пределах витрины: только её направления и её продавцы."""

from django.db.models import Exists, OuterRef, Q, QuerySet

from app.apps.products.models import Category, Product


def scope_products(queryset: QuerySet, storefront) -> QuerySet:
    if not storefront:
        return queryset
    if storefront.verticals:
        queryset = queryset.filter(category__vertical__in=storefront.verticals)
    seller_ids = [seller.pk for seller in storefront.sellers.all()]
    if seller_ids:
        queryset = queryset.filter(seller_id__in=seller_ids)
    return queryset


def scope_categories(queryset: QuerySet, storefront) -> QuerySet:
    if storefront and storefront.verticals:
        queryset = queryset.filter(vertical__in=storefront.verticals)
    return queryset


def with_products(queryset: QuerySet, storefront) -> QuerySet:
    """Только категории, где (с учётом подкатегорий, до 3 уровней) есть товары на витрине."""
    products = scope_products(Product.objects.filter(variants__available=True), storefront)
    in_tree = (
        Q(category=OuterRef("pk")) | Q(category__parent=OuterRef("pk")) | Q(category__parent__parent=OuterRef("pk"))
    )
    return queryset.filter(Exists(products.filter(in_tree)))


def depth(category: Category) -> int:
    """0 — направление/корень, 1 — раздел, 2 — категория (дерево catalog/taxonomy.py)."""
    level, node = 0, category
    while node.parent_id and level < 5:
        level, node = level + 1, node.parent
    return level
