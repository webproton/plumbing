import logging
import secrets

from app.apps.callback.models import SiteSettings
from app.apps.products.models import Product

from .models import TelegramPost
from .telegram import post_product

logger = logging.getLogger(__name__)
MAX_ANNOUNCE = 20  # за один раз (массовая публикация не заваливает канал)


def ensure_feeds_token(shop: SiteSettings, regenerate: bool = False) -> str:
    if regenerate or not shop.feeds_token:
        shop.feeds_token = secrets.token_urlsafe(18)[:24]
        if shop.pk:
            SiteSettings.objects.filter(pk=shop.pk).update(feeds_token=shop.feeds_token)
    return shop.feeds_token


def publish(product: Product, shop: SiteSettings | None = None) -> TelegramPost:
    shop = shop or SiteSettings.current()
    message_id = post_product(product, shop.telegram_channel)
    return TelegramPost.objects.create(product=product, channel=shop.telegram_channel, message_id=message_id)


def announce(product_ids) -> int:
    """Новинки (стали видимыми) → в очередь на автопубликацию, если она включена. Один раз на товар."""
    from kombu.exceptions import OperationalError

    from .tasks import announce_product_task

    shop = SiteSettings.current()
    if not (shop.telegram_autopost and shop.telegram_channel):
        return 0
    posted = set(TelegramPost.objects.filter(product_id__in=product_ids).values_list("product_id", flat=True))
    fresh = [pid for pid in product_ids if pid not in posted][:MAX_ANNOUNCE]
    for i, pid in enumerate(fresh):
        try:
            # пауза между сообщениями: Telegram ограничивает частоту постов в канал
            announce_product_task.apply_async(args=[pid], countdown=i * 4)
        except OperationalError:
            logger.warning("Очередь недоступна — товары не опубликованы в Telegram")
            return i
    return len(fresh)
