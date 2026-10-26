"""Какая витрина у запроса: заголовок X-Storefront (slug) → ?storefront= → домен (X-Storefront-Host или Host)."""

from django.core.cache import cache
from django.utils.functional import SimpleLazyObject

from .models import Storefront, normalize_host

DOMAINS_CACHE_KEY = "storefronts:domains"
DOMAINS_TTL = 60  # новый домен в админке начинает работать в течение минуты


def _domains() -> dict[str, int]:
    mapping = cache.get(DOMAINS_CACHE_KEY)
    if mapping is None:
        mapping = {
            host: storefront.pk
            for storefront in Storefront.objects.filter(is_active=True).exclude(domains="")
            for host in storefront.domain_list
        }
        cache.set(DOMAINS_CACHE_KEY, mapping, DOMAINS_TTL)
    return mapping


def resolve(request) -> Storefront | None:
    active = Storefront.objects.filter(is_active=True).prefetch_related("sellers")
    slug = request.META.get("HTTP_X_STOREFRONT") or request.GET.get("storefront")
    if slug:
        return active.filter(slug=slug.strip().lower()).first()
    # фронтенд передаёт домен, на который зашёл покупатель; прямой запрос к API — его собственный Host
    host = request.META.get("HTTP_X_STOREFRONT_HOST") or request.META.get("HTTP_HOST", "")
    pk = _domains().get(normalize_host(host)) if host else None
    return active.filter(pk=pk).first() if pk else None


class StorefrontMiddleware:
    """request.storefront — витрина запроса или None (общий магазин). Определяется при первом обращении."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.storefront = SimpleLazyObject(lambda: resolve(request))
        return self.get_response(request)


def current(request) -> Storefront | None:
    storefront = getattr(request, "storefront", None)
    # SimpleLazyObject(None) — «пустая» витрина: сравниваем то, что внутри
    return storefront if storefront else None
