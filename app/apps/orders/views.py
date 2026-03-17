from django.db.models import Q
from django.conf import settings
from app.apps.callback.views import send_telegram_message, TELEGRAM_MANAGERS, TELEGRAM_BOT_TOKEN, current_manager_index
from rest_framework.decorators import action
from django.contrib.auth import get_user_model
from rest_framework import viewsets, permissions, mixins, status, serializers
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.response import Response
import html
import logging
from app.apps.orders.permissions import CanManageCartPermission , IsCartOwnerOrAnonWithUUID
from .utils import send_order_confirmation_email,send_order_to_manager_email
from .serializers import (
    OrderListSerializer,
    OrderDetailSerializer,
    CartDetailSerializer,
    CartCreateSerializer,
    OrderCreateSerializer,
)
from .models import Order, Cart

logger = logging.getLogger(__name__)
logger.debug("Создание заказа")
    
User = get_user_model()


class CartViewSet(
    viewsets.GenericViewSet,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
):
    """create cart"""
    throttle_classes = [AnonRateThrottle, UserRateThrottle]
    serializer_class = CartDetailSerializer
    permission_classes = [permissions.AllowAny,  CanManageCartPermission , IsCartOwnerOrAnonWithUUID]


    def get_queryset(self):
        cart_uuid = self.request.GET.get("cart_uuid")
        if self.request.user.is_authenticated:

            # Для авторизованных пользователей ищем корзины по текущему пользователю
            qs = Cart.objects.filter(
                Q(customer=self.request.user) | Q(customer=None),
                orders=None
            )
        else:
            # Для анонимных пользователей ищем корзины по cart_uuid
            qs = Cart.objects.filter(
                customer=None,
                orders=None,
                cart_uuid=cart_uuid
            )
        return qs
    
    def get_serializer_class(self):
        if self.action == "create":
            return CartCreateSerializer
        return CartDetailSerializer
    
    def perform_create(self, serializer):
        if self.request.user.is_authenticated is False:
            serializer.save(customer=None)
        else:
            serializer.save(customer=self.request.user)
            
    @action(detail=False, methods=["get"], url_path="by-uuid")
    def get_by_uuid(self, request):
        cart_uuid = request.GET.get("cart_uuid")
        if not cart_uuid:
            return Response({"detail": "cart_uuid is required"}, status=400)

        cart = self.get_queryset().filter(cart_uuid=cart_uuid).first()
        if not cart:
            return Response({"detail": "Cart not found"}, status=404)

        serializer = self.get_serializer(cart)
        return Response(serializer.data)


class OrderListView(
    viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin
):
    """List of orders with fields: customer name,
    date, total price, number of dishes, status.Orders API for a logged in user"""

    permission_classes = [permissions.AllowAny]
    serializer_class = OrderListSerializer

    def get_queryset(self):
        return Order.objects.filter(customer=self.request.user)

    def get_serializer_class(self):
        """on assignment. in the detailed information
        about the restaurant"""
        if self.action == "retrieve":
            return OrderDetailSerializer
        return self.serializer_class
    
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        order = self.get_object()

        if order.customer != request.user:
            return Response(
                {"detail": "Вы не можете отменить этот заказ."},
                status=status.HTTP_403_FORBIDDEN
            )

        if order.payment_status != Order.PAYMENT_STATUS.waiting_for_payment:
            return Response(
                {"detail": "Отменить можно только заказ, ожидающий оплату."},
                status=status.HTTP_400_BAD_REQUEST
            )

        order.status_order = Order.STATUS.canceled
        order.payment_status = Order.PAYMENT_STATUS.canceled
        order.save()

        return Response({"detail": "Заказ успешно отменён."}, status=status.HTTP_200_OK)

class OrderView(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """Order. Create an order."""

    # permission_classes = [permissions.IsAuthenticated]
    permission_classes = [permissions.AllowAny]
    serializer_class = OrderCreateSerializer
    
    def get_queryset(self):
        # Возвращаем пустой queryset, так как для создания заказов он не нужен
        return Order.objects.none()
    def create(self, request, *args, **kwargs):
        logger.info(f"New order received: cart_id={request.data.get('cart')}, customer_authenticated={request.user.is_authenticated}")

        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):

        global current_manager_index  # обязательно для изменения индекса
        # Проверяем, аутентифицирован ли пользователь
        if self.request.user.is_authenticated:
            cart = serializer.validated_data['cart']

            # Проверка, если корзина пуста
            if not cart.cart_items.exists():
                raise serializers.ValidationError("Корзина пуста, невозможно создать заказ.")
            
            # Создание заказа с аутентифицированным пользователем
            order = serializer.save(customer=self.request.user, total_price=cart.calculate_total_price())

        else:
            order = serializer.save(customer=None)

        # Отправка подтверждения заказа
        send_order_confirmation_email(self.request.user, order)

        # send_order_to_manager_email(order, "manager@example.com")

        # Отправка уведомления менеджеру в Telegram
        assigned_manager = None
        if TELEGRAM_MANAGERS and TELEGRAM_BOT_TOKEN:
            manager_chat_id = TELEGRAM_MANAGERS[current_manager_index]
            current_manager_index = (current_manager_index + 1) % len(TELEGRAM_MANAGERS)

            # ищем менеджера по telegram chat_id
            assigned_manager = User.objects.filter(telegram=manager_chat_id).first()

            # если не нашли — оставляем None
            if assigned_manager:
                order.manager = assigned_manager
                order.save(update_fields=["manager"])

            # --- сообщение в Telegram ---
            cart_items = order.cart.cart_items.all()
            product_list = "\n".join([
                f"{item.product.name} - {item.quantity} шт. x {item.product.variants.first().price} ₴ = {item.total_price} ₴"
                for item in cart_items
            ])

            customer_name = html.escape(order.customer_name)
            comment = html.escape(order.comment or "—")

            text = (
                f"📞 <b>Новый заказ</b>\n\n"
                f"Имя: {customer_name}\n"
                # f"Имя: {order.customer_name}\n"
                f"Телефон: {order.phone_number}\n"
                f"Email: {order.email or '—'}\n"
                f"Адрес: {order.address}, {order.city},\n"
                # f"Адрес: {order.address}, {order.city}, {order.region}, {order.country}, {order.zip_code}\n"

                f"Telegram: {order.telegram or '—'}\n"
                f"WhatsApp: {order.whatsapp or '—'}\n"
                # f"Комментарий: {order.comment or '—'}\n"
                f"Комментарий: {comment}\n"
                f"Тип оплаты: {order.payment_type}\n\n"
                f"Список товаров:\n{product_list}\n"
                f"Общая стоимость: {order.total_price} ₴"
            )

            send_telegram_message(manager_chat_id, text)

        return order

