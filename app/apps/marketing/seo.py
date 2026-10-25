"""Данные для sitemap.xml витрины: что показывать поисковикам (видимые товары и непустые категории)."""

from django.conf import settings
from django.core.cache import cache
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app.apps.products.models import Category, Product

CACHE_KEY = "seo:sitemap"
CACHE_SECONDS = 15 * 60
MAX_PRODUCTS = 45_000  # один sitemap — до 50 000 адресов; каждый товар даёт две языковые версии


def sitemap_data() -> dict:
    products = (
        Product.objects.filter(variants__available=True, slug__isnull=False)
        .exclude(slug="")
        .distinct()
        .order_by("-modified")
        .values("slug", "modified", "photo")[:MAX_PRODUCTS]
    )
    categories = (
        Category.objects.filter(products__variants__available=True, slug__isnull=False)
        .exclude(slug="")
        .distinct()
        .order_by("name")
        .values("slug", "modified")
    )
    return {
        "products": [
            {"slug": p["slug"], "updated": p["modified"].date().isoformat(), "image": _media(p["photo"])}
            for p in products
        ],
        "categories": [{"slug": c["slug"], "updated": c["modified"].date().isoformat()} for c in categories],
    }


def _media(path: str | None) -> str | None:
    return f"{settings.MEDIA_URL}{path}" if path else None


class SitemapDataView(APIView):
    """GET /api/seo/sitemap/ — список адресов для sitemap.xml (кэш 15 минут)."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        data = cache.get(CACHE_KEY)
        if data is None:
            data = sitemap_data()
            cache.set(CACHE_KEY, data, CACHE_SECONDS)
        return Response(data)
