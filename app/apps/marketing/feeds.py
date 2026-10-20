"""
Фиды товаров для маркетплейсов и рекламы.

prom.yml     — Prom.ua (YML)
rozetka.yml  — Rozetka (YML, name_ua / stock_quantity)
google.xml   — Google Merchant Center (RSS 2.0 + g:); этот же файл принимают Facebook/Instagram и TikTok Catalog

В фид попадают видимые на сайте варианты с ценой. Каждый вариант — отдельное предложение,
варианты одного товара связаны group_id / item_group_id.
"""

import re
from dataclasses import dataclass
from decimal import Decimal
from html import unescape
from xml.etree import ElementTree as ET

from django.conf import settings
from django.db.models import Prefetch
from django.utils import timezone

from app.apps.products.models import Product, ProductPhoto, ProductVariant
from app.apps.warehouse.labels import is_ean13

G = "http://base.google.com/ns/1.0"
ET.register_namespace("g", G)
_TAGS = re.compile(r"<[^>]+>")


@dataclass
class Offer:
    id: int
    group_id: int | None
    name: str
    url: str
    price: Decimal
    old_price: Decimal | None
    in_stock: bool
    quantity: int
    pictures: list
    category_id: int | None
    category: str
    brand: str
    sku: str
    barcode: str
    description: str


def _base() -> str:
    return settings.FRONTEND_URL.rstrip("/")


def _absolute(url: str | None) -> str | None:
    if not url:
        return None
    return url if url.startswith("http") else f"{_base()}{url}"


def plain(text: str | None, limit: int = 5000) -> str:
    return re.sub(r"\s+", " ", unescape(_TAGS.sub(" ", text or ""))).strip()[:limit]


def offers() -> list[Offer]:
    variants = (
        ProductVariant.objects.filter(available=True, price__isnull=False, product__name__isnull=False)
        .select_related("product__category", "brand")
        .prefetch_related(Prefetch("product__photos", queryset=ProductPhoto.objects.order_by("id")))
        .order_by("product_id", "id")
    )
    counts = {}
    for v in variants:
        counts[v.product_id] = counts.get(v.product_id, 0) + 1
    result = []
    for v in variants:
        p: Product = v.product
        several = counts[v.product_id] > 1
        name = p.name or ""
        if several and v.variant_name and v.variant_name != p.name:
            # «хром» → «Змішувач Grohe хром»; если название варианта уже полное — оставляем как есть
            name = v.variant_name if (p.name or "").lower() in v.variant_name.lower() else f"{p.name} {v.variant_name}"
        pictures = [_absolute(v.photo.url) if v.photo else None, _absolute(p.photo.url) if p.photo else None]
        pictures += [_absolute(ph.photo.url) for ph in p.photos.all() if ph.photo]
        pictures = list(dict.fromkeys(x for x in pictures if x))[:10]
        stock = max(v.stock - v.reserved, Decimal(0))
        result.append(
            Offer(
                id=v.pk,
                group_id=p.pk if several else None,
                name=(name or p.name or "").strip(),
                url=f"{_base()}/product/{p.slug}" + (f"?v={v.pk}" if several else ""),
                price=v.price.quantize(Decimal("0.01")),
                old_price=v.original_price.quantize(Decimal("0.01")) if v.discount and v.original_price else None,
                in_stock=stock > 0,
                quantity=int(stock),
                pictures=pictures,
                category_id=p.category_id,
                category=p.category.name if p.category else "",
                brand=(v.brand.name or "") if v.brand else "",
                sku=v.code or "",
                barcode=(v.barcode or "").strip(),
                description=p.description or v.description or "",
            )
        )
    return result


def _sub(parent, tag, text=None, **attrs):
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrs.items()})
    if text is not None:
        el.text = str(text)
    return el


def _xml(root) -> bytes:
    ET.indent(root, space=" ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def yml(kind: str, shop_name: str) -> bytes:
    """Prom.ua (kind="prom") и Rozetka (kind="rozetka")."""
    items = offers()
    root = ET.Element("yml_catalog", date=timezone.localtime().strftime("%Y-%m-%d %H:%M"))
    shop = _sub(root, "shop")
    _sub(shop, "name", shop_name)
    _sub(shop, "company", shop_name)
    _sub(shop, "url", _base())
    currencies = _sub(shop, "currencies")
    _sub(currencies, "currency", id="UAH", rate="1")
    categories = _sub(shop, "categories")
    for cid, cname in sorted({(o.category_id, o.category) for o in items if o.category_id}):
        _sub(categories, "category", cname, id=cid)
    offers_el = _sub(shop, "offers")
    for o in items:
        attrs = {"id": o.id, "available": "true" if o.in_stock else "false"}
        if o.group_id:
            attrs["group_id"] = o.group_id
        offer = _sub(offers_el, "offer", **attrs)
        _sub(offer, "url", o.url)
        _sub(offer, "price", o.price)
        if o.old_price:
            _sub(offer, "oldprice" if kind == "prom" else "price_old", o.old_price)
        _sub(offer, "currencyId", "UAH")
        if o.category_id:
            _sub(offer, "categoryId", o.category_id)
        for pic in o.pictures:
            _sub(offer, "picture", pic)
        if o.brand:
            _sub(offer, "vendor", o.brand)
        if o.sku:
            _sub(offer, "vendorCode", o.sku)
        if o.barcode and is_ean13(o.barcode):
            _sub(offer, "barcode", o.barcode)
        _sub(offer, "name", o.name)
        _sub(offer, "description", plain(o.description))
        if kind == "rozetka":
            _sub(offer, "name_ua", o.name)
            _sub(offer, "description_ua", plain(o.description))
            _sub(offer, "stock_quantity", o.quantity)
        else:
            _sub(offer, "quantity_in_stock", o.quantity)
    return _xml(root)


def google(shop_name: str) -> bytes:
    """Google Merchant Center / Meta (Facebook, Instagram) / TikTok Catalog."""
    root = ET.Element("rss", version="2.0")
    channel = _sub(root, "channel")
    _sub(channel, "title", shop_name)
    _sub(channel, "link", _base())
    _sub(channel, "description", shop_name)

    def g(parent, tag, value):
        if value not in (None, ""):
            _sub(parent, f"{{{G}}}{tag}", value)

    for o in offers():
        item = _sub(channel, "item")
        g(item, "id", o.id)
        g(item, "title", o.name[:150])
        g(item, "description", plain(o.description) or o.name)
        g(item, "link", o.url)
        g(item, "image_link", o.pictures[0] if o.pictures else None)
        for pic in o.pictures[1:]:
            g(item, "additional_image_link", pic)
        g(item, "availability", "in_stock" if o.in_stock else "out_of_stock")
        if o.old_price:
            g(item, "price", f"{o.old_price} UAH")
            g(item, "sale_price", f"{o.price} UAH")
        else:
            g(item, "price", f"{o.price} UAH")
        g(item, "brand", o.brand)
        gtin = o.barcode if o.barcode and is_ean13(o.barcode) else ""
        g(item, "gtin", gtin)
        g(item, "mpn", o.sku)
        if not gtin and not o.brand:
            g(item, "identifier_exists", "no")
        g(item, "condition", "new")
        g(item, "product_type", o.category)
        g(item, "item_group_id", o.group_id)
    return _xml(root)
