"""
Уведомления о заказах: письмо клиенту и сообщение менеджеру в Telegram.
Вызываются после коммита транзакции; ошибки доставки логируются и не влияют на заказ.
TODO(шаг 5): перенести в Celery-задачи с retry.
"""

import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

from app.core import telegram

from .models import Order

logger = logging.getLogger(__name__)
User = get_user_model()


def _items_text(order):
    return "\n".join(
        f"{item.name} — {item.quantity.normalize()} × {item.unit_price} ₴ = {item.line_total} ₴"
        for item in order.items.all()
    )


def send_customer_email(order: Order):
    recipient = order.email or (order.customer.email if order.customer_id else None)
    if not recipient:
        return
    message = (
        f"Здравствуйте, {order.customer_name or 'уважаемый клиент'}!\n\n"
        f"Ваш заказ №{order.pk} принят.\n\n"
        f"{_items_text(order)}\n\n"
        f"Итого: {order.total_price} ₴\n\n"
        "Мы свяжемся с вами для подтверждения.\n"
    )
    try:
        send_mail(f"Заказ №{order.pk} принят", message, settings.DEFAULT_FROM_EMAIL, [recipient])
    except Exception as exc:  # SMTP недоступен — заказ уже создан, только логируем
        logger.error("Не удалось отправить письмо по заказу %s: %s", order.pk, exc)


def send_manager_telegram(order: Order):
    chat_id = telegram.next_manager_chat_id()
    if not chat_id:
        return
    manager = User.objects.filter(telegram=chat_id).first()
    if manager and not order.manager_id:
        Order.objects.filter(pk=order.pk).update(manager=manager)

    e = telegram.esc
    text = (
        f"📦 <b>Новый заказ №{order.pk}</b>\n\n"
        f"Имя: {e(order.customer_name)}\n"
        f"Телефон: {e(order.phone_number)}\n"
        f"Email: {e(order.email)}\n"
        f"Город: {e(order.city)}, отделение: {e(order.department_number)}\n"
        f"Адрес: {e(order.address)}\n"
        f"Telegram: {e(order.telegram)} · WhatsApp: {e(order.whatsapp)}\n"
        f"Комментарий: {e(order.comment)}\n"
        f"Оплата: {e(order.get_payment_type_display())}\n\n"
        f"{e(_items_text(order))}\n\n"
        f"<b>Итого: {order.total_price} ₴</b>"
    )
    telegram.send_message(chat_id, text)


def notify_order_created(order_id: int):
    order = Order.objects.select_related("customer").prefetch_related("items").get(pk=order_id)
    send_customer_email(order)
    send_manager_telegram(order)
