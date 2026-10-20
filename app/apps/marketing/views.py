import hmac
from urllib.parse import urlsplit

from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.callback.models import SiteSettings
from app.apps.products.manage import CanEditProduct
from app.apps.products.services import editable_products
from app.apps.warehouse.permissions import get_active_seller

from . import feeds
from .models import TelegramPost
from .services import publish
from .telegram import TelegramError

FEEDS = {"prom.yml": "prom", "rozetka.yml": "rozetka", "google.xml": "google"}
CACHE_SECONDS = 30 * 60


def feed_view(request, token: str, name: str):
    """Фид по секретной ссылке /api/feeds/<token>/<prom.yml|rozetka.yml|google.xml> (кэш 30 минут)."""
    shop = SiteSettings.current()
    kind = FEEDS.get(name)
    if not (kind and shop.feeds_enabled and shop.feeds_token and hmac.compare_digest(token, shop.feeds_token)):
        raise Http404
    key = f"feed:{kind}:{shop.feeds_token}"
    content = cache.get(key)
    if content is None:
        title = shop.legal_name or settings_site_name()
        content = feeds.google(title) if kind == "google" else feeds.yml(kind, title)
        cache.set(key, content, CACHE_SECONDS)
    response = HttpResponse(content, content_type="application/xml; charset=utf-8")
    response["Cache-Control"] = f"public, max-age={CACHE_SECONDS}"
    return response


def settings_site_name() -> str:
    return settings.SITE_NAME or urlsplit(settings.FRONTEND_URL).hostname or "Shop"


class TelegramPublishView(APIView):
    """POST /api/marketing/telegram/products/<id>/ — опубликовать товар в канал сейчас."""

    permission_classes = [CanEditProduct]

    def post(self, request, pk):
        user = request.user
        product = editable_products(user, get_active_seller(user)).prefetch_related("variants").filter(pk=pk).first()
        if product is None:
            raise Http404
        self.check_object_permissions(request, product)
        try:
            post = publish(product)
        except TelegramError as exc:
            raise ValidationError({"detail": str(exc)}) from None
        return Response({"posted_at": post.posted_at, "channel": post.channel})

    def get(self, request, pk):
        last = TelegramPost.objects.filter(product_id=pk).first()
        shop = SiteSettings.current()
        return Response(
            {
                "enabled": bool(shop.telegram_channel),
                "posted_at": last.posted_at if last else None,
                "channel": shop.telegram_channel,
            }
        )
