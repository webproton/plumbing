from rest_framework.permissions import BasePermission
from app.apps.orders.models import Cart

class CanManageCartPermission(BasePermission):
    """
    Проверяет, может ли пользователь создать или обновить корзину.
    """

    def has_permission(self, request, view):
        user = request.user
        cart_uuid = request.data.get("cart_uuid")

        # Для авторизованного пользователя
        if user.is_authenticated:
            return True  # Разрешаем доступ, чтобы метод create мог обработать логику корзины

        # Для анонимного пользователя
        if cart_uuid:
            # Проверяем, существует ли корзина с переданным cart_uuid
            return Cart.objects.filter(cart_uuid=cart_uuid, customer=None, orders=None).exists()
        else:
            return True  # Разрешаем создание новой корзины, если cart_uuid не передан



class IsCartOwnerOrAnonWithUUID(BasePermission):
    """
    Проверяет, что авторизованный пользователь может видеть только свои корзины.
    Анонимный пользователь может получить доступ только через cart_uuid.
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        cart_uuid = request.query_params.get("cart_uuid") or request.data.get("cart_uuid")

        if user.is_authenticated:
            # Авторизованный пользователь может получить доступ только к своей корзине
            return obj.customer == user
        elif cart_uuid:
            # Анонимный пользователь получает доступ только через cart_uuid
            return obj.cart_uuid == cart_uuid

        # Если cart_uuid отсутствует, доступ запрещен
        return False