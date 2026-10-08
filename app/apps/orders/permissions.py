from rest_framework.permissions import BasePermission


class IsCartOwnerOrAnonWithUUID(BasePermission):
    """
    Авторизованный пользователь — только свои корзины.
    Аноним — только анонимная корзина, и только зная её cart_uuid.
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_authenticated:
            return obj.customer_id == request.user.pk
        cart_uuid = request.query_params.get("cart_uuid") or request.data.get("cart_uuid")
        # obj.cart_uuid — UUID, из запроса приходит строка: сравниваем строковые представления
        return obj.customer_id is None and bool(cart_uuid) and str(obj.cart_uuid) == str(cart_uuid)
