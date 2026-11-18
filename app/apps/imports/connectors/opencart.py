"""
Публичный сайт поставщика на OpenCart (svit-mebliv.in.ua и подобные): каталог без выгрузки — обходим разделы.

Поставщик дал ссылку на сайт как каталог (цены дилера — отдельным прайсом): адаптер проходит от главной по
разделам и их страницам (?page=N), страница с разметкой schema.org Product — товар. Берём название, код товару,
описание, все фото, характеристики (вкладка «Характеристики»), цену, бренд, раздел (хлебные крошки).
Вежливо: пауза между запросами (0,5 с), не больше max_pages страниц и max_products товаров за синхронизацию,
служебные адреса (корзина, сравнение, сортировка, фильтры) не открываем — как велит robots.txt сайта.
"""

import html
import json
import re
import time
from urllib.parse import urljoin, urlsplit

from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from ..formats import build_item
from .base import ConnectorError, FetchedCatalog
from .web import SiteAdapter, register

SKIP = re.compile(
    r"(route=|/image/|\.(?:jpe?g|png|webp|gif|svg|pdf|css|js|ico)(?:$|\?)|[?&](?:sort|order|limit|filter_\w+|search|tag)=|"
    r"/(?:cart|checkout|account|login|wishlist|compare|contact|blog|information|specials?)\b|#)",
    re.IGNORECASE,
)
LINK = re.compile(r"""href\s*=\s*["']([^"'#]+)["']""", re.IGNORECASE)
JSONLD = re.compile(r"""<script[^>]+application/ld\+json[^>]*>(.*?)</script>""", re.IGNORECASE | re.DOTALL)
# «Код товару:</span> <span>bianco …</span>» — между подписью и значением любые теги
CODE = re.compile(r"(?:Код товару|Код товара|Артикул|Модель)\s*:?\s*(?:<[^>]+>\s*)*([^<\n]{1,100})", re.IGNORECASE)
SPEC_ROW = re.compile(r"<tr[^>]*>\s*<td[^>]*>(.*?)</td>\s*<td[^>]*>(.*?)</td>\s*</tr>", re.IGNORECASE | re.DOTALL)
# характеристики блоками: <div class="…attribut…-list-item"><div>Корпус</div><div>ДСП</div></div>
SPEC_DIV = re.compile(
    r"""class=["'][^"']*attribut\w*-list-item[^"']*["'][^>]*>\s*<div[^>]*>(.*?)</div>\s*<div[^>]*>(.*?)</div>""",
    re.IGNORECASE | re.DOTALL,
)
DESCRIPTION = re.compile(
    r"""id=["'](?:product_description|tab-description|product-description)["'][^>]*>(.*?)(?=<div[^>]+class=["'][^"']*tab-pane|$)""",
    re.IGNORECASE | re.DOTALL,
)
BIG_IMAGE = re.compile(
    r"""(?:href|data-(?:zoom-)?image|data-large|data-src)\s*=\s*["']([^"']+/image/(?:cache/)?catalog/[^"']+\.(?:jpe?g|png|webp))["']""",
    re.IGNORECASE,
)
TAG = re.compile(r"<[^>]+>")


def _text(fragment: str) -> str:
    return " ".join(html.unescape(TAG.sub(" ", fragment or "")).split())


def _products_from_jsonld(page: str) -> list[dict]:
    found = []
    for raw in JSONLD.findall(page):
        try:
            data = json.loads(html.unescape(raw.strip()))
        except ValueError:
            continue
        nodes = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        found += [n for n in nodes if isinstance(n, dict) and n.get("@type") in ("Product", ["Product"])]
    return found


def _breadcrumbs(page: str) -> list[str]:
    for raw in JSONLD.findall(page):
        try:
            data = json.loads(html.unescape(raw.strip()))
        except ValueError:
            continue
        if isinstance(data, dict) and data.get("@type") == "BreadcrumbList":
            items = sorted(data.get("itemListElement", []), key=lambda i: i.get("position", 0))
            return [str((i.get("item") or {}).get("name") or i.get("name") or "") for i in items]
    return []


def _as_list(value) -> list:
    if not value:
        return []
    return value if isinstance(value, list) else [value]


def _large(url: str) -> str:
    """Миниатюра OpenCart (image/cache/catalog/…-300x300.jpg) → оригинал image/catalog/….jpg."""
    url = url.replace("/image/cache/catalog/", "/image/catalog/")
    return re.sub(r"-\d{2,4}x\d{2,4}(\.\w+)$", r"\1", url)


def parse_product(page: str, url: str) -> dict | None:
    """Страница товара → значения для build_item (+ характеристики). None — не товар."""
    products = _products_from_jsonld(page)
    if not products:
        return None
    product = products[0]
    offers = _as_list(product.get("offers"))
    offer = offers[0] if offers and isinstance(offers[0], dict) else {}
    photos = []
    for image in [*_as_list(product.get("image")), *BIG_IMAGE.findall(page)]:
        full = urljoin(url, _large(str(image)))
        if full not in photos and "/catalog/" in full and "logo" not in full.lower() and "icon" not in full.lower():
            photos.append(full)
    code = CODE.search(page)
    description = DESCRIPTION.search(page)
    brand = product.get("brand")
    crumbs = [c for c in _breadcrumbs(page) if c][1:-1]  # без «Головна» и самого товара
    availability = str(offer.get("availability") or "")
    params = {}
    for name, value in [*SPEC_ROW.findall(page), *SPEC_DIV.findall(page)]:
        name, value = _text(name), _text(value)
        if name and value and len(name) < 120 and name.lower() not in ("код товару", "код товара"):
            params.setdefault(name, value)
    values = {
        "external_id": url,
        "sku": (_text(code.group(1)) if code else "")
        or str(product.get("model") or product.get("sku") or product.get("mpn") or ""),
        "name": _text(str(product.get("name") or "")),
        "brand": (brand.get("name") if isinstance(brand, dict) else str(brand or "")),
        # «Комоди, Комоди, Фріда …» — первый раздел
        "category": " / ".join(crumbs[-2:]) if crumbs else str(product.get("category") or "").split(",")[0].strip(),
        # вкладка «Опис» полнее, чем описание в разметке
        "description": (description.group(1)[:30000] if description else "")
        or html.unescape(str(product.get("description") or "")),
        "url": url,
        "price": offer.get("price"),
        "currency": offer.get("priceCurrency") or "UAH",
        "available": ("InStock" in availability) if availability else None,
        "photos": photos,
    }
    return {"values": values, "params": params}


@register
class OpencartSiteAdapter(SiteAdapter):
    code = "opencart_site"
    needs_login = False
    title = gettext_lazy("Публичный сайт на OpenCart (каталог без выгрузки)")
    description = gettext_lazy(
        "Обходит разделы сайта поставщика и забирает товары: название, код, описание, все фото, характеристики, цену. "
        "Ссылка источника — главная страница сайта."
    )
    option_fields = {
        "start_urls": gettext_lazy("Разделы, с которых начать (по одному в строке; пусто — с главной)"),
        "max_products": gettext_lazy("Максимум товаров за синхронизацию (по умолчанию 3000)"),
        "delay_seconds": gettext_lazy("Пауза между запросами, сек (по умолчанию 0,5)"),
    }

    def login(self) -> None:  # сайт открытый
        return None

    def _page(self, url: str) -> str:
        return self.get(url).content.decode("utf-8", errors="replace")

    def catalog(self) -> FetchedCatalog:
        root = self.source.url
        if not root:
            raise ConnectorError(_("Укажите ссылку на главную страницу сайта поставщика"))
        host = urlsplit(root).netloc
        starts = [u.strip() for u in str(self.option("start_urls", "") or "").splitlines() if u.strip()] or [root]
        max_products = int(self.option("max_products", 3000) or 3000)
        max_pages = max(max_products * 3, 300)
        delay = float(self.option("delay_seconds", 0.5) or 0)
        queue, seen, items, errors = [urljoin(root, u) for u in starts], set(), [], 0
        menu: set[str] = set()  # ссылки, которые есть на каждой странице (меню) — обходим в последнюю очередь
        while queue and len(seen) < max_pages and len(items) < max_products:
            url = queue.pop(0).split("#")[0]
            if url in seen:
                continue
            seen.add(url)
            try:
                page = self._page(url)
            except Exception:  # noqa: BLE001 — одна битая страница не останавливает обход
                errors += 1
                continue
            if delay:
                time.sleep(delay)
            product = parse_product(page, url)
            if product:
                item = build_item(product["values"], product["params"])
                if item:
                    items.append(item)
                continue
            links = []
            for href in LINK.findall(page):
                link = urljoin(url, html.unescape(href)).split("#")[0]
                if urlsplit(link).netloc == host and link not in seen and not SKIP.search(link) and link not in links:
                    links.append(link)
            if not menu:
                menu = set(links)  # первая страница: её ссылки — общее меню сайта
                queue.extend(links)
            else:
                # новое на этой странице (товары раздела, ?page=2) — сразу, меню — в конец
                fresh = [link for link in links if link not in menu]
                queue[:0] = fresh
                queue.extend(link for link in links if link in menu)
        if not items:
            raise ConnectorError(_("На сайте не найдено ни одного товара — проверьте ссылку на сайт"))
        return FetchedCatalog(items, {"format": "opencart", "pages": len(seen), "errors": errors})
