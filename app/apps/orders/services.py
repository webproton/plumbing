"""
Бизнес-логика заказов: оформление из корзины, смена статусов, связь со складом.

Жизненный цикл товара по заказу (Order.stock_state):
    оформление            → reserved     (stock.reserve: доступно к продаже уменьшается)
    отмена                → released     (stock.release)
    доставлен / завершён  → written_off  (stock.write_off_reserved: физическое списание со склада)

Позиция «под заказ» (OrderItem.on_order): своего товара не хватало, а у поставщика есть. Её не резервируют;
продавец заказывает товар, оприходует накладную, и при отгрузке он списывается со склада как обычно.
"""

import logging
from decimal import Decimal

from django.db import transaction
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from app.apps.imports.services import order_suppliers
from app.apps.products.models import ProductVariant
from app.apps.warehouse import stock
from app.apps.warehouse.permissions import get_active_seller
from app.core.tasks import enqueue

from . import customer_notifications
from .models import Cart, CartItems, CustomerNotification, Order, OrderItem
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


def _stock_lines(order, *, on_order=False):
    return [(item.variant_id, item.quantity) for item in order.items.all() if item.on_order == on_order]


def _split_on_order(lines) -> set[int]:
    """Варианты, которые уйдут «под заказ»: своего не хватает на всю строку, а у поставщика хватает."""
    ids = sorted({variant.pk for _ci, variant in lines})
    locked = {v.pk: v for v in ProductVariant.objects.select_for_update().filter(pk__in=ids).order_by("pk")}
    on_order = set()
    for ci, variant in lines:
        v = locked[variant.pk]
        if v.available_stock < ci.quantity and v.supplier_qty and v.supplier_qty >= ci.quantity:
            on_order.add(v.pk)
    return on_order


@transaction.atomic
def create_order_from_cart(
    cart: Cart, *, user=None, allow_on_order=True, notify=True, discount_percent=0, **order_fields
) -> Order:
    """
    Оформляет заказ: фиксирует позиции и цены, резервирует товар. Всё или ничего.
    Корзина блокируется — двойной клик / параллельный запрос не создаст второй заказ.
    allow_on_order=False — только свой остаток (касса: товар в руках, «под заказ» не продаём);
    discount_percent — скидка в цене каждой позиции (прибыль в статистике считается от цены продажи).
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

    on_order = _split_on_order(lines) if allow_on_order else set()
    own = [(variant, ci.quantity) for ci, variant in lines if variant.pk not in on_order]
    if own:
        stock.reserve(own)
    suppliers = order_suppliers(on_order) if on_order else {}

    order_fields.setdefault("language", customer_notifications.order_language())
    order = Order.objects.create(
        cart=cart,
        customer=user if user is not None and user.is_authenticated else None,
        # всё «под заказ» — резервировать нечего
        stock_state=Order.STOCK_STATE.reserved if own else Order.STOCK_STATE.none,
        total_price=Decimal("0"),
        discount_percent=discount_percent,
        **order_fields,
    )
    items = [
        OrderItem(
            order=order,
            product=ci.product,
            variant=variant,
            name=variant.variant_name or ci.product.name or "",
            sku=variant.code or "",
            unit_price=_discounted(variant.price, discount_percent),
            unit_cost=variant.cost_price,
            quantity=ci.quantity,
            on_order=variant.pk in on_order,
            supplier=suppliers.get(variant.pk),
        )
        for ci, variant in lines
    ]
    OrderItem.objects.bulk_create(items)
    order.total_price = sum((i.line_total for i in items), Decimal("0"))
    order.save(update_fields=["total_price"])

    # письмо и Telegram — в фоне, чтобы не задерживать ответ покупателю
    if notify:
        transaction.on_commit(lambda: enqueue(notify_order_created_task, order.pk, run_inline_on_failure=True))
    return order


def _discounted(price: Decimal, percent: int) -> Decimal:
    return (price * (100 - percent) / 100).quantize(Decimal("0.01")) if percent else price


POS_DISCOUNTS = (0, 1, 2, 3, 4, 5)


@transaction.atomic
def create_pos_sale(user, lines, *, payment_method: str, discount_percent: int = 0) -> Order:
    """
    Продажа на точке «человеку с улицы» (касса в кабинете продавца): без покупателя, доставки и писем.
    lines: [(variant_id, количество)]. Оплачено сразу, заказ «Завершён», товар тут же списан со своего склада.
    Своего остатка по учёту не хватает — ошибка с подсказкой (сначала приход или пересчёт), продажа не проходит.
    """
    seller = get_active_seller(user)
    if seller is None and not user.is_superuser:
        raise ValidationError({"detail": _("Продавать может только одобренный продавец")})
    if payment_method not in Order.PAYMENT_METHOD:
        raise ValidationError({"payment_method": _("Оберіть спосіб оплати: готівка, картка або переказ")})
    if discount_percent not in POS_DISCOUNTS:
        raise ValidationError({"discount_percent": _("Знижка на місці — від 0 до 5 %")})
    quantities: dict[int, int] = {}
    for variant_id, qty in lines:
        try:
            variant_id, qty = int(variant_id), int(qty)
        except (TypeError, ValueError):
            raise ValidationError({"lines": _("Неправильна позиція продажу")}) from None
        if qty <= 0:
            raise ValidationError({"lines": _("Кількість має бути більше нуля")})
        quantities[variant_id] = quantities.get(variant_id, 0) + qty
    if not quantities:
        raise ValidationError({"lines": _("Додайте хоча б один товар")})
    variants = {v.pk: v for v in ProductVariant.objects.select_related("product").filter(pk__in=quantities)}
    for variant_id in quantities:
        variant = variants.get(variant_id)
        if variant is None or (seller is not None and variant.product.seller_id != seller.pk):
            raise ValidationError({"lines": _("Товар не знайдено серед ваших (id {id})").format(id=variant_id)})

    cart = Cart.objects.create(customer=None)
    CartItems.objects.bulk_create(
        CartItems(cart=cart, product=variants[vid].product, variant=variants[vid], quantity=qty)
        for vid, qty in quantities.items()
    )
    try:
        order = create_order_from_cart(
            cart,
            allow_on_order=False,
            notify=False,
            discount_percent=discount_percent,
            customer_name=_("Покупець на місці"),
            address=_("Продаж на місці"),
            channel=Order.CHANNEL.pos,
            payment_method=payment_method,
            payment_status=Order.PAYMENT_STATUS.paid_for,
            manager=user,
        )
    except stock.InsufficientStockError as error:
        variant = variants.get(error.context.get("variant_id"))
        raise ValidationError({
            "lines": _("«{name}»: за обліком на складі {available}, а продаєте {qty}. Спершу оприходуйте товар "
                       "або виправте залишок у режимі «Перерахунок».").format(
                name=(variant.variant_name or variant.product.name) if variant else "?",
                available=error.context.get("available"), qty=error.context.get("requested"),
            )
        }) from None
    return change_status(order, Order.STATUS.completed, user=user)


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
            comment = _("Заказ #{pk}").format(pk=order.pk)
            own, ordered = _stock_lines(order), _stock_lines(order, on_order=True)
            if own:
                stock.write_off_reserved(
                    own, user=user, comment=comment, from_reserve=order.stock_state == Order.STOCK_STATE.reserved
                )
            if ordered:  # товар от поставщика уже должен лежать на складе — по накладной
                try:
                    stock.write_off_reserved(ordered, user=user, comment=comment, from_reserve=False)
                except stock.InsufficientStockError:
                    raise ValidationError(
                        {"status_order": _("Товар «под заказ» ещё не оприходован — примите накладную от поставщика")}
                    ) from None
            order.stock_state = Order.STOCK_STATE.written_off

    elif order.stock_state == Order.STOCK_STATE.released:
        raise ValidationError({"status_order": _("Отменённый заказ нельзя вернуть в работу")})

    order.status_order = new_status
    order.save(update_fields=["status_order", "payment_status", "stock_state"])
    event = {
        Order.STATUS.delivering: CustomerNotification.EVENTS.shipped,
        Order.STATUS.canceled: CustomerNotification.EVENTS.canceled,
    }.get(new_status)
    if event:
        customer_notifications.schedule(order.pk, event)
    return order


def cancel_by_customer(order: Order, user) -> Order:
    if order.customer_id != user.pk:
        raise ValidationError({"detail": _("Вы не можете отменить этот заказ")})
    if order.payment_status != Order.PAYMENT_STATUS.waiting_for_payment:
        raise ValidationError({"detail": _("Отменить можно только заказ, ожидающий оплаты")})
    if order.status_order not in (Order.STATUS.in_processing,):
        raise ValidationError({"detail": _("Заказ уже передан в доставку")})
    return change_status(order, Order.STATUS.canceled, user=user)
