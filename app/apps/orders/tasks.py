from celery import shared_task

from .customer_notifications import notify
from .notifications import notify_order_created


@shared_task(name="orders.notify_order_created")
def notify_order_created_task(order_id: int):
    notify_order_created(order_id)


@shared_task(name="orders.notify_customer")
def notify_customer_task(order_id: int, event: str):
    notify(order_id, event)
