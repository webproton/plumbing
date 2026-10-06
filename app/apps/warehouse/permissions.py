# warehouse/permissions.py

from rest_framework import permissions

from .models import *



class IsSellerWarehouseOwner(permissions.BasePermission):
    """Только владелец продавца может работать со своими складами/движениями"""
    
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True

        seller_profile = getattr(request.user, 'seller_profile', None)
        if not seller_profile:
            return False

        if isinstance(obj, (Warehouse, StockMovement, InventoryDocument)):
            return obj.seller == seller_profile
        if isinstance(obj, Supplier):
            return True  # поставщики общие
        return False
    
    # def has_object_permission(self, request, view, obj):
    #     if request.user.is_superuser:
    #         return True
    #     seller_profile = getattr(request.user, 'seller_profile', None)
        
    #     if hasattr(request.user, 'seller_profile'):
    #         if isinstance(obj, Warehouse):
    #             return obj.seller == request.user.seller_profile
    #         if isinstance(obj, StockMovement):
    #             return obj.seller == request.user.seller_profile
    #         if isinstance(obj, InventoryDocument):
    #             return obj.seller == request.user.seller_profile
    #         if isinstance(obj, Supplier):
    #             return True  # поставщики общие
    #     return False
    

    def has_permission(self, request, view):
        # Суперюзер всегда может
        if request.user.is_superuser:
            return True
        
        # Чтение разрешено всем аутентифицированным продавцам
        seller_profile = getattr(request.user, 'seller_profile', None)
        if request.method in permissions.SAFE_METHODS :
            return seller_profile is not None and seller_profile.is_active
        
        # Запись только для активных продавцов
        seller_profile = getattr(request.user, 'seller_profile', None)
        return seller_profile is not None and seller_profile.is_active


class IsSellerOrAdminReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated and (
            request.user.is_superuser or hasattr(request.user, 'seller_profile')
        )