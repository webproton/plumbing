"""
Бизнес-логика заказов: оформление из корзины, смена статусов, связь со складом.

Жизненный цикл товара по заказу (Order.stock_state):
    оформление            → reserved     (stock.reserve: доступно к продаже уменьшается)
    отмена                → released     (stock.release)
    доставлен / завершён  → written_off  (stock.write_off_reserved: физическое списание со склада)
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from app.apps.warehouse import stock
from app.core.tasks import enqueue

from .models import Cart, Order, OrderItem
from .tasks import notify_order_created_task

logger = logging.getLogger(__name__)

SHIPPED_STATUSES = {Order.STATUS.delivered, Order.STATUS.completed}


def _resolve_variant(cart_item):
    """Позиция корзины без варианта допустима, только если у товара ровно один вариант."""
    if cart_item.variant_id:
        return cart_item.variant
    variants = list(cart_item.product.variants.all()[:2])
    if len(variants) == 1:
        return variants[0]
    raise ValidationError({"cart": _("Для товара «{name}» не выбран вариант").format(name=cart_item.product.name)})


def _stock_lines(order):
    return [(item.variant_id, item.quantity) for item in order.items.all()]


@transaction.atomic
def create_order_from_cart(cart: Cart, *, user=None, **order_fields) -> Order:
    """
    Оформляет заказ: фиксирует позиции и цены, резервирует товар. Всё или ничего.
    Корзина блокируется — двойной клик / параллельный запрос не создаст второй заказ.
    """
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    if Order.objects.filter(cart=cart).exists():
        raise ValidationError({"cart": _("Заказ для этой корзины уже оформлен")})

    cart_items = list(cart.cart_items.select_related("product", "variant"))
    if not cart_items:
        raise ValidationError({"cart": _("Корзина пуста, невозможно создать заказ")})

    lines = []
    for ci in cart_items:
        variant = _resolve_variant(ci)
        if variant.price is None:
            raise ValidationError({"cart": _("У товара «{name}» не указана цена").format(name=ci.product.name)})
        lines.append((ci, variant))

    stock.reserve([(variant, ci.quantity) for ci, variant in lines])

    order = Order.objects.create(
        cart=cart,
        customer=user if user is not None and user.is_authenticated else None,
        stock_state=Order.STOCK_STATE.reserved,
        total_price=Decimal("0"),
        **order_fields,
    )
    items = [
        OrderItem(
            order=order,
            product=ci.product,
            variant=variant,
            name=variant.variant_name or ci.product.name or "",
            sku=variant.code or "",
            unit_price=variant.price,
            quantity=ci.quantity,
        )
        for ci, variant in lines
    ]
    OrderItem.objects.bulk_create(items)
    order.total_price = sum((i.line_total for i in items), Decimal("0"))
    order.save(update_fields=["total_price"])

    # письмо и Telegram — в фоне, чтобы не задерживать ответ покупателю
    transaction.on_commit(lambda: enqueue(notify_order_created_task, order.pk, run_inline_on_failure=True))
    return order


@transaction.atomic
def change_status(order: Order, new_status: str, *, user=None) -> Order:
    """Меняет статус заказа и синхронизирует склад."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status_order == new_status:
        return order

    if new_status == Order.STATUS.canceled:
        if order.stock_state == Order.STOCK_STATE.written_off:
            raise ValidationError({"status_order": _("Товар уже списан со склада — оформите возврат")})
        if order.stock_state == Order.STOCK_STATE.reserved:
            stock.release(_stock_lines(order))
            order.stock_state = Order.STOCK_STATE.released
        order.payment_status = Order.PAYMENT_STATUS.canceled

    elif new_status in SHIPPED_STATUSES:
        if order.stock_state == Order.STOCK_STATE.released:
            raise ValidationError({"status_order": _("Заказ был отменён — резерв снят")})
        if order.stock_state in (Order.STOCK_STATE.reserved, Order.STOCK_STATE.none):
            stock.write_off_reserved(
                _stock_lines(order),
                user=user,
                comment=f"Заказ #{order.pk}",
                from_reserve=order.stock_state == Order.STOCK_STATE.reserved,
            )
            order.stock_state = Order.STOCK_STATE.written_off

    elif order.stock_state == Order.STOCK_STATE.released:
        raise ValidationError({"status_order": _("Отменённый заказ нельзя вернуть в работу")})

    order.status_order = new_status
    order.save(update_fields=["status_order", "payment_status", "stock_state"])
    return order


def cancel_by_customer(order: Order, user) -> Order:
    if order.customer_id != user.pk:
        raise ValidationError({"detail": _("Вы не можете отменить этот заказ")})
    if order.payment_status != Order.PAYMENT_STATUS.waiting_for_payment:
        raise ValidationError({"detail": _("Отменить можно только заказ, ожидающий оплаты")})
    if order.status_order not in (Order.STATUS.in_processing,):
        raise ValidationError({"detail": _("Заказ уже передан в доставку")})
    return change_status(order, Order.STATUS.canceled, user=user)
