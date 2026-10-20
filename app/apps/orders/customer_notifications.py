"""
Письма покупателю о заказе: принят, отправлен (с ТТН), ТТН появилась позже, посылка в отделении,
оплата получена, заказ отменён. Язык — тот, на котором оформляли заказ (Order.language).

schedule(order_id, event) вызывается внутри транзакции — письмо уходит в фоне после коммита.
Каждое событие отправляется один раз: CustomerNotification.key уникален в заказе. Журнал писем
виден менеджеру в карточке заказа; неудачное письмо можно отправить ещё раз (resend).
Выключатель — «Уведомлять покупателей по email» в настройках магазина.
"""

import logging
from decimal import Decimal

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.utils import timezone, translation

from app.apps.callback.models import SiteSettings
from app.core.tasks import enqueue

from .models import CustomerNotification, Order

logger = logging.getLogger(__name__)

TRACK_URL = "https://novaposhta.ua/tracking/?cargo_number={ttn}"
EVENT = CustomerNotification.EVENTS
STATUS = CustomerNotification.STATUSES

TEXTS = {
    "uk": {
        "greeting": "Вітаємо, {name}!",
        "greeting_anon": "Вітаємо!",
        "created.subject": "Замовлення №{number} прийнято",
        "created.body": ["Дякуємо за замовлення! Ми отримали його й незабаром зв'яжемося з вами для підтвердження."],
        "shipped.subject": "Замовлення №{number} відправлено",
        "shipped.body": ["Ваше замовлення передано Новій Пошті.", "Номер ТТН: {ttn}"],
        "shipped.body_nottn": [
            "Ваше замовлення передано в доставку.",
            "Номер ТТН надішлемо окремим листом, щойно він з'явиться.",
        ],
        "ttn.subject": "ТТН для замовлення №{number}",
        "ttn.body": ["Номер ТТН вашого замовлення: {ttn}"],
        "arrived.subject": "Замовлення №{number} чекає на вас у відділенні",
        "arrived.body": [
            "Посилка {ttn} прибула у відділення Нової Пошти{place}.",
            "Не забудьте її забрати — термін безкоштовного зберігання обмежений.",
        ],
        "paid.subject": "Оплату за замовлення №{number} отримано",
        "paid.body": ["Дякуємо! Оплату отримано — готуємо замовлення до відправлення."],
        "canceled.subject": "Замовлення №{number} скасовано",
        "canceled.body": ["Ваше замовлення скасовано. Якщо це помилка або у вас є запитання — зв'яжіться з нами."],
        "items": "Склад замовлення",
        "total": "Разом",
        "track": "Відстежити посилку",
        "open": "Переглянути замовлення",
        "contacts": "Наші контакти",
        "auto": "Лист надіслано автоматично.",
    },
    "ru": {
        "greeting": "Здравствуйте, {name}!",
        "greeting_anon": "Здравствуйте!",
        "created.subject": "Заказ №{number} принят",
        "created.body": ["Спасибо за заказ! Мы получили его и скоро свяжемся с вами для подтверждения."],
        "shipped.subject": "Заказ №{number} отправлен",
        "shipped.body": ["Ваш заказ передан Новой Почте.", "Номер ТТН: {ttn}"],
        "shipped.body_nottn": [
            "Ваш заказ передан в доставку.",
            "Номер ТТН пришлём отдельным письмом, как только он появится.",
        ],
        "ttn.subject": "ТТН для заказа №{number}",
        "ttn.body": ["Номер ТТН вашего заказа: {ttn}"],
        "arrived.subject": "Заказ №{number} ждёт вас в отделении",
        "arrived.body": [
            "Посылка {ttn} прибыла в отделение Новой Почты{place}.",
            "Не забудьте её забрать — срок бесплатного хранения ограничен.",
        ],
        "paid.subject": "Оплата за заказ №{number} получена",
        "paid.body": ["Спасибо! Оплата получена — готовим заказ к отправке."],
        "canceled.subject": "Заказ №{number} отменён",
        "canceled.body": ["Ваш заказ отменён. Если это ошибка или у вас есть вопросы — свяжитесь с нами."],
        "items": "Состав заказа",
        "total": "Итого",
        "track": "Отследить посылку",
        "open": "Посмотреть заказ",
        "contacts": "Наши контакты",
        "auto": "Письмо отправлено автоматически.",
    },
}


def order_language() -> str:
    """Язык текущего запроса (его выставляет LocaleMiddleware по Accept-Language витрины)."""
    return "ru" if (translation.get_language() or "").startswith("ru") else "uk"


def schedule(order_id: int, event: str):
    """Письмо покупателю после коммита текущей транзакции (в фоне; без очереди — сразу)."""
    from .tasks import notify_customer_task

    transaction.on_commit(lambda: enqueue(notify_customer_task, order_id, event, run_inline_on_failure=True))


def _key(order: Order, event: str) -> str | None:
    if event in (EVENT.ttn, EVENT.arrived):
        return f"{event}:{order.ttn}" if order.ttn else None
    return event


def notify(order_id: int, event: str) -> CustomerNotification | None:
    """Отправить письмо о событии, если оно ещё не уходило. None — письмо не нужно."""
    order = Order.objects.select_related("customer").prefetch_related("items").get(pk=order_id)
    if not SiteSettings.current().notify_customers:
        return None
    key = _key(order, event)
    if key is None:
        return None
    if (
        event == EVENT.ttn
        and order.notifications.filter(event=EVENT.shipped, ttn=order.ttn, status=STATUS.sent).exists()
    ):
        return None  # номер уже был в письме «отправлен»
    return _send(order, event, key)


def resend(note: CustomerNotification) -> CustomerNotification:
    """Отправить письмо ещё раз (кнопка менеджера) — даже если уведомления выключены."""
    order = Order.objects.select_related("customer").prefetch_related("items").get(pk=note.order_id)
    return _send(order, note.event, note.key, force=True)


def _recipient(order: Order) -> str:
    return order.email or (order.customer.email if order.customer_id and order.customer else "") or ""


def _send(order: Order, event: str, key: str, *, force=False) -> CustomerNotification | None:
    recipient = _recipient(order)
    if not recipient:
        return None
    with transaction.atomic():
        note, _created = CustomerNotification.objects.get_or_create(
            order=order, key=key, defaults={"event": event, "recipient": recipient, "ttn": order.ttn}
        )
        note = CustomerNotification.objects.select_for_update().get(pk=note.pk)
        if note.status == STATUS.sent and not force:
            return note
        note.recipient, note.ttn = recipient, order.ttn
        try:
            _message(order, event, recipient).send()
        except Exception as exc:  # SMTP недоступен — заказ не страдает, менеджер видит ошибку и может повторить
            logger.warning("Письмо покупателю по заказу %s (%s) не отправлено: %s", order.pk, event, exc)
            note.status, note.error = STATUS.failed, str(exc)[:500]
        else:
            note.status, note.error, note.sent_at = STATUS.sent, "", timezone.now()
        note.save(update_fields=["recipient", "ttn", "status", "error", "sent_at"])
    return note


def format_money(value) -> str:
    return f"{Decimal(value or 0):,.2f}".replace(",", " ").replace(".", ",")


def format_qty(value) -> str:
    return f"{Decimal(value).quantize(Decimal('0.001')):f}".rstrip("0").rstrip(".")


def _message(order: Order, event: str, recipient: str) -> EmailMultiAlternatives:
    lang = order.language if order.language in TEXTS else "uk"
    t = TEXTS[lang]
    shop = SiteSettings.current()
    values = {"number": order.pk, "ttn": order.ttn, "place": f": {order.address}" if order.address else ""}
    body_key = f"{event}.body_nottn" if event == EVENT.shipped and not order.ttn else f"{event}.body"

    button = None
    if event in (EVENT.shipped, EVENT.ttn, EVENT.arrived) and order.ttn:
        button = (t["track"], TRACK_URL.format(ttn=order.ttn))
    elif order.customer_id:
        prefix = "/ru" if lang == "ru" else ""
        button = (t["open"], f"{settings.FRONTEND_URL.rstrip('/')}{prefix}/account/orders/{order.pk}")

    context = {
        "lang": lang,
        "t": t,
        "shop_name": settings.SITE_NAME or shop.legal_name,
        "greeting": t["greeting"].format(name=order.customer_name) if order.customer_name else t["greeting_anon"],
        "paragraphs": [p.format(**values) for p in t[body_key]],
        "items": [
            {
                "name": i.name,
                "qty": format_qty(i.quantity),
                "price": format_money(i.unit_price),
                "total": format_money(i.line_total),
            }
            for i in order.items.all()
        ]
        if event == EVENT.created
        else [],
        "total": format_money(order.total_price),
        "button": button,
        "contacts": [c for c in (shop.phone, shop.email) if c],
    }
    message = EmailMultiAlternatives(
        subject=t[f"{event}.subject"].format(**values),
        body=render_to_string("orders/email/customer.txt", context),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[recipient],
        reply_to=[shop.email] if shop.email else None,
    )
    message.attach_alternative(render_to_string("orders/email/customer.html", context), "text/html")
    return message
