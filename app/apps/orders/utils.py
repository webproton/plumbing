import re
from rest_framework.exceptions import ValidationError
from django.core.mail import send_mail
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


def validate_phone_number(value):
    """
    Проверка номера телефона Украины:
    - Допускаются форматы: +380XXXXXXXXX или 0XXXXXXXXX
    - Преобразует 0XXXXXXXXX в +380XXXXXXXXX
    """
    value = re.sub(r'\D', '', value)  # оставляем только цифры

    if value.startswith("0") and len(value) == 10:
        value = "+380" + value[1:]

    elif value.startswith("380") and len(value) == 12:
        value = "+" + value

    else:
        raise ValidationError(
            "Номер телефона должен быть в формате +380XXXXXXXXX"
        )

    return value

def send_order_confirmation_email(user, order):
    """
    Отправляет письмо с подтверждением заказа пользователю.
    """

    # Определяем имя пользователя для приветствия
    if user.is_authenticated:
        full_name = f"{user.first_name} {user.last_name}".strip() or order.customer_name or "Уважаемый клиент"
    else:
        full_name = order.customer_name or "Уважаемый клиент"

    # Формируем список продуктов
    cart_items = order.cart.cart_items.all()
    product_list = "\n".join([
        f"{item.product.name} - {item.quantity} шт. x {item.product.variants.first().price} ₴ = {item.total_price} ₴"
        for item in cart_items
    ])

    # Формируем письмо
    subject = "Ваш заказ успешно создан!"
    message = (
        f"Здравствуйте, {full_name}!\n\n"
        f"Ваш заказ с номером {order.id} успешно создан.\n"
        f"Общая стоимость: {order.total_price} ₴.\n\n"
        f"Список товаров:\n{product_list}\n\n"
        "Спасибо за покупку! Мы свяжемся с вами для дальнейшей информации.\n\n"
        "Письмо автоматически сгенерировано ботом"
    )

    # Определяем email: сначала email из заказа, потом у пользователя
    recipient_list = []
    if order.email:
        recipient_list.append(order.email)
    elif user.is_authenticated and user.email:
        recipient_list.append(user.email)

    if not recipient_list:
        logger.warning(f"Не указан email для заказа #{order.id}, письмо не отправлено")
        return

    try:
        send_mail(subject, message, "Luxora mebel", recipient_list, fail_silently=False)
        logger.info(f"Order confirmation email sent to {recipient_list}")
    except Exception as e:
        logger.error(f"Failed to send order confirmation email: {e}")




def send_order_to_manager_email(order, manager_email):
    cart_items = order.cart.cart_items.all()
    product_list = "\n".join([
        f"{item.product.name} - {item.quantity} шт. x {item.product.variants.first().price} ₴ = {item.total_price} ₴"
        for item in cart_items
    ])
    
    subject = f"Новый заказ #{order.id}"
    message = (
        f"Имя: {order.customer_name}\n"
        f"Телефон: {order.phone_number}\n"
        f"Email: {order.email or '—'}\n"
        f"Адрес: {order.address}, {order.city}\n"
        f"Telegram: {order.telegram or '—'}\n"
        f"WhatsApp: {order.whatsapp or '—'}\n"
        f"Комментарий: {order.comment or '—'}\n"
        f"Тип оплаты: {order.payment_type}\n\n"
        f"Список товаров:\n{product_list}\n"
        f"Общая стоимость: {order.total_price} ₴"
    )
    
    send_mail(subject, message, settings.EMAIL_HOST_USER, [manager_email])