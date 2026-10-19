"""ТТН Новой Почты в заказах: ввод вручную, создание через API, обновление статуса посылки."""

import logging
import re

from django.db import transaction
from django.utils import timezone
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

from app.apps.callback.models import SiteSettings
from app.apps.orders.models import Order
from app.apps.orders.services import change_status

from . import novaposhta as np

logger = logging.getLogger(__name__)

TTN_RE = re.compile(r"^\d{14}$")
ACTIVE = (Order.STATUS.in_processing, Order.STATUS.delivering)


def _phone(order) -> str:
    return re.sub(r"\D", "", order.phone_number or "")


def _mark_shipped(order, user=None):
    """Есть ТТН — заказ в доставке (склад не меняется: списание — при «Доставлен»)."""
    if order.status_order == Order.STATUS.in_processing:
        change_status(order, Order.STATUS.delivering, user=user)


@transaction.atomic
def set_ttn(order: Order, number: str, *, user=None) -> Order:
    number = re.sub(r"\s+", "", number or "")
    if number and not TTN_RE.match(number):
        raise ValidationError({"ttn": _("Номер ТТН — 14 цифр")})
    Order.objects.filter(pk=order.pk).update(
        ttn=number, ttn_ref="", ttn_status="", ttn_status_code="", ttn_updated_at=None
    )
    order.refresh_from_db()
    if number:
        _mark_shipped(order, user)
    return order


def create_ttn(order: Order, *, weight, seats=1, description="", payer="Recipient", cod=False, user=None) -> Order:
    if order.ttn:
        raise ValidationError({"ttn": _("У заказа уже есть ТТН")})
    if not (order.np_city_ref and order.np_warehouse_ref):
        raise ValidationError({"ttn": _("В заказе нет отделения из справочника Новой Почты — введите ТТН вручную")})
    shop = SiteSettings.current()
    try:
        doc = np.create_document(
            city_ref=order.np_city_ref,
            warehouse_ref=order.np_warehouse_ref,
            recipient_name=order.customer_name,
            recipient_phone=_phone(order),
            sender_city_ref=shop.np_sender_city_ref,
            sender_warehouse_ref=shop.np_sender_warehouse_ref,
            sender_phone=re.sub(r"\D", "", shop.np_sender_phone),
            weight=weight,
            seats=seats,
            description=description or _("Сантехника"),
            declared_cost=float(order.total_price or 0),
            payer=payer,
            cod_amount=float(order.total_price) if cod and order.total_price else None,
        )
    except np.NovaPoshtaError as exc:
        raise ValidationError({"ttn": str(exc)}) from None
    with transaction.atomic():
        Order.objects.filter(pk=order.pk).update(
            ttn=doc["number"] or "", ttn_ref=doc["ref"] or "", ttn_status=_("Создана"), ttn_status_code="1",
            ttn_updated_at=timezone.now(),
        )  # fmt: skip
        order.refresh_from_db()
        _mark_shipped(order, user)
    return order


def refresh_statuses(orders) -> int:
    """Обновить статусы посылок; полученные → заказ «Доставлен» (товар списывается со склада)."""
    orders = [o for o in orders if o.ttn]
    if not orders:
        return 0
    rows = {r["number"]: r for r in np.track([(o.ttn, _phone(o)) for o in orders])}
    updated = 0
    for order in orders:
        info = rows.get(order.ttn)
        if not info:
            continue
        Order.objects.filter(pk=order.pk).update(
            ttn_status=info["status"][:255], ttn_status_code=info["code"], ttn_updated_at=timezone.now()
        )
        updated += 1
        if info["code"] in np.RECEIVED_CODES and order.status_order in ACTIVE:
            try:
                with transaction.atomic():
                    change_status(order, Order.STATUS.delivered)
            except Exception:  # noqa: BLE001 — не мешаем обновлению остальных посылок
                logger.exception("Не удалось отметить заказ %s доставленным", order.pk)
    return updated


def orders_to_track():
    since = timezone.now() - timezone.timedelta(days=60)
    return (
        Order.objects.exclude(ttn="")
        .exclude(ttn_status_code__in=np.FINAL_CODES)
        .filter(creation_date__gte=since)
        .order_by("id")
    )
