from celery import shared_task

from .notifications import notify_order_created


@shared_task(name="orders.notify_order_created")
def notify_order_created_task(order_id: int):
    notify_order_created(order_id)
