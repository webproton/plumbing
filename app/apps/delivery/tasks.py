from celery import shared_task

from . import novaposhta as np
from .services import orders_to_track, refresh_statuses


@shared_task(name="delivery.refresh_ttn_statuses")
def refresh_ttn_statuses():
    orders = list(orders_to_track()[:500])
    total = 0
    for start in range(0, len(orders), 100):
        try:
            total += refresh_statuses(orders[start : start + 100])
        except np.NovaPoshtaError:
            break  # API недоступно — попробуем в следующий раз
    return total
