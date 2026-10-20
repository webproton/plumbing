"""
Уведомления о новом заказе: письмо покупателю (customer_notifications) и сообщение менеджеру в Telegram.
Вызываются после коммита транзакции; ошибки доставки логируются и не влияют на заказ.
"""

import logging

from django.contrib.auth import get_user_model

from app.core import telegram

from . import customer_notifications
from .customer_notifications import format_qty
from .models import CustomerNotification, Order

logger = logging.getLogger(__name__)
User = get_user_model()


def _items_text(order):
    return "\n".join(
        f"{item.name} — {format_qty(item.quantity)} × {item.unit_price} ₴ = {item.line_total} ₴"
        for item in order.items.all()
    )


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
    customer_notifications.notify(order_id, CustomerNotification.EVENTS.created)
    send_manager_telegram(Order.objects.prefetch_related("items").get(pk=order_id))
