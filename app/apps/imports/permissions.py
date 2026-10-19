from app.apps.warehouse.permissions import IsWarehouseStaff, get_active_seller


class IsImportStaff(IsWarehouseStaff):
    """Продавец работает только со своими источниками и загрузками, администратор — со всеми."""

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser:
            return True
        seller = get_active_seller(request.user)
        return seller is not None and obj.seller_id == seller.pk
