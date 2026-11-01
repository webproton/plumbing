"""
Заказы в кабинете (/api/orders/manage/): список, карточка, смена статуса (склад синхронизирует
services.change_status), оплата, менеджер, заметка, журнал писем покупателю (+ отправить ещё раз).

Администратор ведёт все заказы. Продавец видит заказы со своими товарами и меняет их, только если
все позиции заказа — его (иначе смена статуса списала бы со склада чужие товары).
"""

from django.core.mail import EmailMessage
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse
from django.utils.translation import gettext as _
from rest_framework import mixins, serializers, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from app.apps.callback.models import SiteSettings
from app.apps.delivery import novaposhta as np
from app.apps.delivery import services as delivery
from app.apps.warehouse.permissions import IsWarehouseStaff, get_active_seller
from app.core.pagination import StandardPagination

from . import customer_notifications
from .invoice import generate_invoice
from .models import CustomerNotification, Order, OrderItem
from .services import change_status, create_pos_sale
from .stats import PERIODS, sales_stats

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
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)

    class Meta:
        model = OrderItem
        fields = ["id", "name", "sku", "quantity", "unit_price", "line_total", "variant", "product", "photo", "available_stock", "on_order", "supplier_name"]  # fmt: skip

    def get_photo(self, item):
        v = item.variant
        if v.photo:
            return v.photo.url
        return v.product.photo.url if v.product_id and v.product.photo else None


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerNotification
        fields = ["id", "event", "status", "recipient", "ttn", "error", "created_at", "sent_at"]


class OrderRowSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_order_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    payment_type_display = serializers.CharField(source="get_payment_type_display", read_only=True)
    channel_display = serializers.CharField(source="get_channel_display", read_only=True)
    payment_method_display = serializers.CharField(source="get_payment_method_display", read_only=True)
    items_count = serializers.IntegerField(read_only=True)
    manager_email = serializers.CharField(source="manager.email", read_only=True, default=None)

    class Meta:
        model = Order
        fields = [
            "id", "creation_date", "customer_name", "phone_number", "email", "address", "total_price",
            "status_order", "status_display", "payment_status", "payment_status_display", "payment_type",
            "payment_type_display", "stock_state", "items_count", "manager_email", "channel", "channel_display",
            "payment_method", "payment_method_display", "discount_percent",
        ]  # fmt: skip


class OrderDetailSerializer(OrderRowSerializer):
    items = ItemSerializer(many=True, read_only=True)
    delivery_tools = serializers.SerializerMethodField()
    next_statuses = serializers.SerializerMethodField()
    can_manage = serializers.SerializerMethodField()
    customer_email = serializers.CharField(source="customer.email", read_only=True, default=None)
    notifications = NotificationSerializer(many=True, read_only=True)
    notify_customers = serializers.SerializerMethodField()

    class Meta(OrderRowSerializer.Meta):
        fields = [
            *OrderRowSerializer.Meta.fields,
            "city", "department_number", "comment", "telegram", "whatsapp", "manager_note", "customer_email",
            "items", "next_statuses", "can_manage", "np_city_ref", "np_warehouse_ref", "ttn", "ttn_status",
            "ttn_status_code", "ttn_updated_at", "delivery_tools", "notifications", "notify_customers", "language",
        ]  # fmt: skip

    def get_next_statuses(self, order):
        return [{"value": s, "label": str(S[s])} for s in NEXT_STATUSES.get(order.status_order, [])]

    def get_can_manage(self, order):
        return can_manage(self.context["request"].user, order)

    def get_notify_customers(self, order):
        return SiteSettings.current().notify_customers

    def get_delivery_tools(self, order):
        shop = SiteSettings.current()
        sender_ready = bool(shop.np_sender_city_ref and shop.np_sender_warehouse_ref and shop.np_sender_phone)
        return {
            "can_create_ttn": np.enabled_ttn() and sender_ready and bool(order.np_warehouse_ref),
            "np_key": np.enabled_ttn(),
            "sender_ready": sender_ready,
            "has_requisites": shop.has_requisites,
        }


class ManageOrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    permission_classes = [IsOrderStaff]

    @action(detail=False, methods=["get"])
    def stats(self, request):
        """Статистика продаж: ?days=1|7|30|90|365 (по умолчанию 30)."""
        try:
            days = int(request.query_params.get("days", 30))
        except ValueError:
            days = 0
        if days not in PERIODS:
            raise ValidationError({"days": _("Период: {periods} дней").format(periods=", ".join(map(str, PERIODS)))})
        return Response(sales_stats(request.user, days))
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
            if p.get("channel") in Order.CHANNEL:
                qs = qs.filter(channel=p["channel"])
            if q := p.get("q", "").strip():
                digits = "".join(ch for ch in q if ch.isdigit())
                cond = Q(customer_name__icontains=q) | Q(email__icontains=q)
                if q.lstrip("#").isdigit():
                    cond |= Q(pk=int(q.lstrip("#")))
                if len(digits) >= 5:
                    cond |= Q(phone_number__contains=digits[-9:])
                qs = qs.filter(cond)
            return qs.order_by("-creation_date")
        return qs.annotate(items_count=Count("items")).prefetch_related("items__variant__product", "notifications")

    def _managed(self):
        order = self.get_object()
        if not can_manage(self.request.user, order):
            raise PermissionDenied(_("В заказе есть товары других продавцов — им управляет администратор"))
        return order

    def _respond(self, order):
        return Response(
            OrderDetailSerializer(self.get_queryset().get(pk=order.pk), context=self.get_serializer_context()).data
        )

    @action(detail=False, methods=["post"], url_path="pos-sale")
    def pos_sale(self, request):
        """Касса на точке: {"lines": [{"variant": id, "quantity": 2}], "payment_method": "cash|card|iban",
        "discount_percent": 0..5} → продажа оплачена, завершена, товар списан."""
        lines = request.data.get("lines") or []
        if not isinstance(lines, list):
            raise ValidationError({"lines": _("Неправильний список товарів")})
        try:
            discount = int(request.data.get("discount_percent") or 0)
        except (TypeError, ValueError):
            discount = -1
        order = create_pos_sale(
            request.user,
            [(line.get("variant"), line.get("quantity")) for line in lines if isinstance(line, dict)],
            payment_method=str(request.data.get("payment_method") or ""),
            discount_percent=discount,
        )
        return self._respond(order)

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
        if value == Order.PAYMENT_STATUS.paid_for and order.payment_status != value:
            customer_notifications.schedule(order.pk, CustomerNotification.EVENTS.paid)
        return self._respond(order)

    @action(detail=True, methods=["post"], url_path=r"notifications/(?P<note_id>\d+)/resend")
    def notification_resend(self, request, pk=None, note_id=None):
        """Отправить письмо покупателю ещё раз (не дошло, покупатель просит повторить)."""
        note = self._managed().notifications.filter(pk=note_id).first()
        if note is None:
            raise ValidationError({"detail": _("Письмо не найдено")})
        if customer_notifications.resend(note) is None:
            raise ValidationError({"detail": _("У покупателя нет email")})
        return self._respond(note.order)

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

    @action(detail=True, methods=["post"])
    def ttn(self, request, pk=None):
        """{"ttn": "20450000000000"} — номер, созданный в кабинете Новой Почты; пусто — убрать."""
        order = delivery.set_ttn(self._managed(), str(request.data.get("ttn") or ""), user=request.user)
        if order.ttn:
            try:
                delivery.refresh_statuses([order])
            except np.NovaPoshtaError:
                pass  # статус подтянется по расписанию
        return self._respond(order)

    @action(detail=True, methods=["post"], url_path="ttn/create")
    def ttn_create(self, request, pk=None):
        """Создать ТТН через API Новой Почты: weight (кг), seats, description, payer (Recipient|Sender), cod."""
        try:
            weight = round(float(request.data.get("weight") or 1), 2)
            seats = int(request.data.get("seats") or 1)
        except (TypeError, ValueError):
            raise ValidationError({"weight": _("Укажите вес числом")}) from None
        if not (0.1 <= weight <= 1000) or not (1 <= seats <= 50):
            raise ValidationError({"weight": _("Проверьте вес и количество мест")})
        payer = "Sender" if request.data.get("payer") == "Sender" else "Recipient"
        order = delivery.create_ttn(
            self._managed(),
            weight=weight,
            seats=seats,
            description=str(request.data.get("description") or "")[:100],
            payer=payer,
            cod=str(request.data.get("cod")).lower() in ("1", "true", "on"),
            user=request.user,
        )
        return self._respond(order)

    @action(detail=True, methods=["post"], url_path="ttn/refresh")
    def ttn_refresh(self, request, pk=None):
        order = self.get_object()
        try:
            delivery.refresh_statuses([order])
        except np.NovaPoshtaError as exc:
            raise ValidationError({"ttn": str(exc)}) from None
        return self._respond(order)

    @action(detail=True, methods=["get"])
    def invoice(self, request, pk=None):
        return invoice_response(self.get_object())

    @action(detail=True, methods=["post"], url_path="invoice/send")
    def invoice_send(self, request, pk=None):
        order = self._managed()
        email = order.email or (order.customer.email if order.customer_id else "")
        if not email:
            raise ValidationError({"detail": _("У покупателя нет email")})
        shop = _shop_with_requisites()
        message = EmailMessage(
            subject=_("Счёт на оплату заказа №{id}").format(id=order.pk),
            body=_("Добрый день! Во вложении счёт на оплату заказа №{id}. После оплаты мы отправим заказ.").format(
                id=order.pk
            ),
            to=[email],
        )
        message.attach(f"invoice-{order.pk}.pdf", generate_invoice(order, shop), "application/pdf")
        message.send(fail_silently=False)
        return Response({"sent_to": email})

    @action(detail=False, methods=["get"])
    def counts(self, request):
        """Количество заказов по статусам (вкладки и счётчик новых в меню)."""
        rows = visible_orders(request.user).values("status_order").annotate(n=Count("id"))
        return Response({r["status_order"]: r["n"] for r in rows})


def _shop_with_requisites():
    shop = SiteSettings.current()
    if not shop.has_requisites:
        raise ValidationError({"detail": _("Заполните реквизиты магазина (получатель и IBAN) в настройках")})
    return shop


def invoice_response(order):
    pdf = generate_invoice(order, _shop_with_requisites())
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="invoice-{order.pk}.pdf"'
    return response
