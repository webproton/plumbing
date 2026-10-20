import logging

from celery import shared_task

from app.apps.callback.models import SiteSettings
from app.apps.products.models import Product

from .models import TelegramPost
from .telegram import TelegramError

logger = logging.getLogger(__name__)


@shared_task(name="marketing.announce_product")
def announce_product_task(product_id: int):
    from .services import publish

    product = Product.objects.prefetch_related("variants").filter(pk=product_id).first()
    shop = SiteSettings.current()
    if product is None or TelegramPost.objects.filter(product=product).exists():
        return
    if not any(v.available for v in product.variants.all()):
        return  # товар успели скрыть
    try:
        publish(product, shop)
    except TelegramError as exc:
        logger.warning("Автопубликация товара %s в Telegram не удалась: %s", product_id, exc)
