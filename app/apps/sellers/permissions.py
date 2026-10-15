from rest_framework import permissions


class IsSellerOwner(permissions.BasePermission):
    """Только владелец продавца может редактировать свои данные"""

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, "seller_profile"):
            return obj == request.user.seller_profile
        return False


class IsSellerOrReadOnly(permissions.BasePermission):
    """Продавец может читать, владелец — редактировать, админ — всё"""

    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        if request.user.is_superuser:
            return True
        if hasattr(request.user, "seller_profile"):
            return obj == request.user.seller_profile
        return False
