import logging

from django.db.models import Prefetch, Q
from rest_framework import mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from . import services
from .models import Cart, CartItems, Order, OrderItem
from .permissions import IsCartOwnerOrAnonWithUUID
from .serializers import (
    CartCreateSerializer,
    CartDetailSerializer,
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
)

logger = logging.getLogger(__name__)


class CartViewSet(viewsets.GenericViewSet, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin):
    permission_classes = [permissions.AllowAny, IsCartOwnerOrAnonWithUUID]

    def get_queryset(self):
        qs = Cart.objects.filter(orders=None).prefetch_related(
            Prefetch("cart_items", queryset=CartItems.objects.select_related("product", "variant"))
        )
        if self.request.user.is_authenticated:
            return qs.filter(customer=self.request.user)
        cart_uuid = self.request.query_params.get("cart_uuid") or self.request.data.get("cart_uuid")
        return qs.filter(customer=None, cart_uuid=cart_uuid) if cart_uuid else qs.none()

    def get_serializer_class(self):
        return CartCreateSerializer if self.action == "create" else CartDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = serializer.save()
        return Response(CartDetailSerializer(cart, context=self.get_serializer_context()).data,
                        status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"], url_path="by-uuid")
    def get_by_uuid(self, request):
        cart_uuid = request.query_params.get("cart_uuid")
        if not cart_uuid:
            return Response({"detail": "cart_uuid is required"}, status=status.HTTP_400_BAD_REQUEST)
        owner = Q(customer=None) | Q(customer=request.user) if request.user.is_authenticated else Q(customer=None)
        cart = self.get_queryset().model.objects.filter(owner, orders=None, cart_uuid=cart_uuid).first()
        if not cart:
            return Response({"detail": "Cart not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(self.get_serializer(cart).data)


class OrderListView(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    """История заказов текущего пользователя."""
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return (
            Order.objects.filter(customer=self.request.user)
            .prefetch_related(Prefetch("items", queryset=OrderItem.objects.select_related("variant", "product")))
            .order_by("-creation_date")
        )

    def get_serializer_class(self):
        return OrderDetailSerializer if self.action == "retrieve" else OrderListSerializer

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        services.cancel_by_customer(self.get_object(), request.user)
        return Response({"detail": "Заказ успешно отменён."})


class OrderView(viewsets.GenericViewSet, mixins.CreateModelMixin):
    """Оформление заказа (в т.ч. гостевое)."""
    permission_classes = [permissions.AllowAny]
    serializer_class = OrderCreateSerializer
    queryset = Order.objects.none()

    def perform_create(self, serializer):
        order = serializer.save()
        logger.info("Создан заказ #%s (пользователь: %s)", order.pk,
                    self.request.user.pk if self.request.user.is_authenticated else "гость")
