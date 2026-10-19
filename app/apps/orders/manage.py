"""
Заказы в кабинете (/api/orders/manage/): список, карточка, смена статуса (склад синхронизирует
services.change_status), оплата, менеджер, заметка.

Администратор ведёт все заказы. Продавец видит заказы со своими товарами и меняет их, только если
все позиции заказа — его (иначе смена статуса списала бы со склада чужие товары).
"""

from django.db.models import Count, Exists, OuterRef, Q
from django.utils.translation import gettext as _
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from app.apps.warehouse.permissions import IsWarehouseStaff, get_active_seller
from app.core.pagination import StandardPagination

from .models import Order, OrderItem
from .services import change_status

S = Order.STATUS
NEXT_STATUSES = {
    S.in_processing: [S.delivering, S.delivered, S.completed, S.canceled],
    S.delivering: [S.delivered, S.completed, S.canceled],
    S.delivered: [S.completed],
    S.completed: [],
    S.canceled: [],
}


class IsOrderStaff(IsWarehouseStaff):
    """Кабинет; доступ к конкретному заказу уже ограничен выборкой visible_orders."""

    def has_object_permission(self, request, view, obj):
        return True


def visible_orders(user):
    if user.is_superuser:
        return Order.objects.all()
    seller = get_active_seller(user)
    if seller is None:
        return Order.objects.none()
    mine = OrderItem.objects.filter(order=OuterRef("pk"), product__seller=seller)
    return Order.objects.filter(Exists(mine))


def can_manage(user, order) -> bool:
    if user.is_superuser:
        return True
    seller = get_active_seller(user)
    return bool(seller) and not order.items.exclude(product__seller=seller).exists()


class ItemSerializer(serializers.ModelSerializer):
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    photo = serializers.SerializerMethodField()
    available_stock = serializers.DecimalField(
        source="variant.available_stock", max_digits=12, decimal_places=3, read_only=True
    )

    class Meta:
        model = OrderItem
        fields = ["id", "name", "sku", "quantity", "unit_price", "line_total", "variant", "product", "photo", "available_stock"]  # fmt: skip

    def get_photo(self, item):
        v = item.variant
        if v.photo:
            return v.photo.url
        return v.product.photo.url if v.product_id and v.product.photo else None


class OrderRowSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_order_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    payment_type_display = serializers.CharField(source="get_payment_type_display", read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    manager_email = serializers.CharField(source="manager.email", read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            "id", "creation_date", "customer_name", "phone_number", "email", "address", "total_price",
            "status_order", "status_display", "payment_status", "payment_status_display", "payment_type",
            "payment_type_display", "stock_state", "items_count", "manager_email",
        ]  # fmt: skip


class OrderDetailSerializer(OrderRowSerializer):
    items = ItemSerializer(many=True, read_only=True)
    next_statuses = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source="customer.email", read_only=True, default=None)

    class Meta(OrderRowSerializer.Meta):
        fields = [
            *OrderRowSerializer.Meta.fields,
            "city", "department_number", "comment", "telegram", "whatsapp", "manager_note", "customer_email",
            "items", "next_statuses", "can_manage",
        ]  # fmt: skip

    def get_next_statuses(self, order):
        return [{"value": s, "label": str(S[s])} for s in NEXT_STATUSES.get(order.status_order, [])]

    def get_can_manage(self, order):
        return can_manage(self.context["request"].user, order)


class ManageOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrderStaff]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        return OrderRowSerializer if self.action == "list" else OrderDetailSerializer

    def get_queryset(self):
        qs = visible_orders(self.request.user).select_related("manager", "customer")
        if self.action == "list":
            qs = qs.annotate(items_count=Count("items"))
            p = self.request.query_params
            if p.get("status") in S:
                qs = qs.filter(status_order=p["status"])
            if p.get("payment") in Order.PAYMENT_STATUS:
                qs = qs.filter(payment_status=p["payment"])
            if q := p.get("q", "").strip():
                digits = "".join(ch for ch in q if ch.isdigit())
                cond = Q(customer_name__icontains=q) | Q(email__icontains=q)
                if q.lstrip("#").isdigit():
                    cond |= Q(pk=int(q.lstrip("#")))
                if len(digits) >= 5:
                    cond |= Q(phone_number__contains=digits[-9:])
                qs = qs.filter(cond)
            return qs.order_by("-creation_date")
        return qs.annotate(items_count=Count("items")).prefetch_related("items__variant__product")

    def _managed(self):
        order = self.get_object()
        if not can_manage(self.request.user, order):
            raise PermissionDenied(_("В заказе есть товары других продавцов — им управляет администратор"))
        return order

    def _respond(self, order):
        return Response(
            OrderDetailSerializer(self.get_queryset().get(pk=order.pk), context=self.get_serializer_context()).data
        )

    @action(detail=True, methods=["post"])
    def status(self, request, pk=None):
        order = self._managed()
        new = request.data.get("status")
        if new not in NEXT_STATUSES.get(order.status_order, []):
            raise ValidationError({"status": _("Такой переход статуса невозможен")})
        change_status(order, new, user=request.user)
        if order.manager_id is None:
            Order.objects.filter(pk=order.pk).update(manager=request.user)
        return self._respond(order)

    @action(detail=True, methods=["post"])
    def payment(self, request, pk=None):
        order = self._managed()
        value = request.data.get("payment_status")
        if value not in Order.PAYMENT_STATUS:
            raise ValidationError({"payment_status": _("Неизвестный статус оплаты")})
        Order.objects.filter(pk=order.pk).update(payment_status=value)
        return self._respond(order)

    @action(detail=True, methods=["post"])
    def note(self, request, pk=None):
        order = self._managed()
        note = str(request.data.get("manager_note") or "")[:2000]
        Order.objects.filter(pk=order.pk).update(manager_note=note)
        return self._respond(order)

    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        order = self._managed()
        Order.objects.filter(pk=order.pk).update(manager=request.user)
        return self._respond(order)

    @action(detail=False, methods=["get"])
    def counts(self, request):
        """Количество заказов по статусам (вкладки и счётчик новых в меню)."""
        rows = visible_orders(request.user).values("status_order").annotate(n=Count("id"))
        return Response({r["status_order"]: r["n"] for r in rows})
