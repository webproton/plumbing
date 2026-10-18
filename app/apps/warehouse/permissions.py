from django.utils.translation import gettext_lazy

# warehouse/permissions.py
from rest_framework import permissions

from .models import InventoryDocument, StockMovement, Supplier, Warehouse


def get_active_seller(user):
    """Профиль продавца, если пользователь — активный и одобренный продавец, иначе None."""
    if not user or not user.is_authenticated:
        return None
    seller = getattr(user, "seller_profile", None)
    if seller is None or not seller.is_approved or not seller.is_active:
        return None
    return seller


class IsWarehouseStaff(permissions.BasePermission):
    """Доступ к складу: суперпользователь или одобренный активный продавец (только свои объекты)."""

    message = gettext_lazy("Доступ к складу есть только у одобренных продавцов.")

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or get_active_seller(user)))

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        seller = get_active_seller(request.user)
        if isinstance(obj, (Warehouse, StockMovement, InventoryDocument)):
            return obj.seller_id == seller.pk
        if isinstance(obj, Supplier):
            return True  # справочник поставщиков общий
        return False


class IsWarehouseStaffOrReadOnly(IsWarehouseStaff):
    """Чтение — любому авторизованному, изменения — продавцу/админу (справочник поставщиков)."""

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user and request.user.is_authenticated)
        return super().has_permission(request, view)
