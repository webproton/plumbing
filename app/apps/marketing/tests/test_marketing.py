"""Фиды (Prom, Rozetka, Google/Meta/TikTok), настройки маркетинга, публикация в Telegram."""

from decimal import Decimal

import pytest
from defusedxml import ElementTree as ET
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.callback.models import SiteSettings
from app.apps.marketing import feeds
from app.apps.marketing import telegram as tg
from app.apps.marketing.models import TelegramPost
from app.apps.products.tests.factories import BrandFactory, CategoryFactory, ProductFactory, ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.tests.factories import SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db
G = "{http://base.google.com/ns/1.0}"


@pytest.fixture
def catalog():
    category = CategoryFactory(name="Змішувачі")
    product = ProductFactory(name="Змішувач Grohe", category=category, description="<p>Хромований &amp; надійний</p>")
    a = ProductVariantFactory(
        product=product,
        variant_name="хром",
        price=Decimal("1000"),
        code="GR-1",
        barcode="4006381333931",
        brand=BrandFactory(name="Grohe"),
        available=True,
    )
    a.discount, a.original_price = 20, Decimal("1250")
    a.save()
    b = ProductVariantFactory(
        product=product,
        variant_name="чорний",
        price=Decimal("1100"),
        code="GR-2",
        barcode="2123456789012",
        brand=None,
        available=True,
    )
    hidden = ProductVariantFactory(price=Decimal("50"), available=False)
    stock.receive(a, WarehouseFactory(), 3, supplier=SupplierFactory())
    return product, a, b, hidden


@override_settings(FRONTEND_URL="https://shop.example")
def test_offers_and_formats(catalog):
    product, a, b, hidden = catalog
    offers = {o.id: o for o in feeds.offers()}
    assert hidden.pk not in offers and set(offers) >= {a.pk, b.pk}
    oa = offers[a.pk]
    assert oa.url == f"https://shop.example/product/{product.slug}?v={a.pk}" and oa.group_id == product.pk
    assert (oa.price, oa.old_price, oa.in_stock, oa.quantity) == (Decimal("1000.00"), Decimal("1250.00"), True, 3)
    assert offers[b.pk].in_stock is False

    prom = ET.fromstring(feeds.yml("prom", "Shop"))
    offer = prom.find(f".//offer[@id='{a.pk}']")
    assert offer.get("available") == "true" and offer.get("group_id") == str(product.pk)
    assert offer.findtext("oldprice") == "1250.00" and offer.findtext("quantity_in_stock") == "3"
    assert offer.findtext("barcode") == "4006381333931" and offer.findtext("description") == "Хромований & надійний"
    assert prom.find(f".//offer[@id='{b.pk}']").find("barcode") is None  # не EAN
    assert prom.find(".//category").text == "Змішувачі"

    rozetka = ET.fromstring(feeds.yml("rozetka", "Shop"))
    r = rozetka.find(f".//offer[@id='{a.pk}']")
    assert (
        r.findtext("price_old") == "1250.00"
        and r.findtext("stock_quantity") == "3"
        and r.findtext("name_ua") == "Змішувач Grohe хром"
    )

    google = ET.fromstring(feeds.google("Shop"))
    items = {i.findtext(f"{G}id"): i for i in google.iter("item")}
    ga, gb = items[str(a.pk)], items[str(b.pk)]
    assert (ga.findtext(f"{G}price"), ga.findtext(f"{G}sale_price")) == ("1250.00 UAH", "1000.00 UAH")
    assert ga.findtext(f"{G}gtin") == "4006381333931" and ga.findtext(f"{G}availability") == "in_stock"
    assert gb.findtext(f"{G}identifier_exists") == "no" and gb.findtext(f"{G}item_group_id") == str(product.pk)


def test_feed_urls_token_and_settings(catalog):
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    url = reverse("callback:shop-settings")
    feed = lambda token, name="prom.yml": APIClient().get(reverse("marketing:feed", args=[token, name]))  # noqa: E731
    assert feed("x").status_code == 404  # фиды выключены

    data = admin.patch(url, {"feeds_enabled": True}, format="json").json()
    token = SiteSettings.current().feeds_token
    assert token and data["feed_urls"]["google.xml"].endswith(f"/api/feeds/{token}/google.xml")
    resp = feed(token)
    assert (
        resp.status_code == 200
        and resp["Content-Type"].startswith("application/xml")
        and b"<yml_catalog" in resp.content
    )
    assert feed(token, "google.xml").status_code == 200 and feed(token, "other.xml").status_code == 404
    assert feed("wrong").status_code == 404

    admin.patch(url, {"regenerate_feeds_token": True, "feeds_enabled": True}, format="json")
    assert SiteSettings.current().feeds_token != token and feed(token).status_code == 404


def test_pixel_ids_are_strict():
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    url = reverse("callback:shop-settings")
    bad = admin.patch(
        url, {"ga4_id": 'G-1234"></script><script>alert(1)</script>', "meta_pixel_id": "12ab"}, format="json"
    )
    assert bad.status_code == 400 and set(bad.json()) >= {"ga4_id", "meta_pixel_id"}
    assert admin.patch(url, {"telegram_channel": "mychan"}, format="json").status_code == 400
    ok = admin.patch(
        url,
        {
            "ga4_id": "g-abc123xyz",
            "gtm_id": "GTM-AB12CD",
            "meta_pixel_id": "123456789012345",
            "tiktok_pixel_id": "C1234567890ABCDEFGHI",
            "telegram_channel": "@my_shop_ua",
        },
        format="json",
    )
    assert ok.status_code == 200 and ok.json()["ga4_id"] == "G-ABC123XYZ"
    public = APIClient().get(reverse("callback:site-settings")).json()
    assert public["gtm_id"] == "GTM-AB12CD" and "iban" not in public


class FakeTelegram:
    def __init__(self):
        self.calls = []

    def __call__(self, url, json=None, timeout=None):
        self.calls.append((url.rsplit("/", 1)[-1], json))
        return type("R", (), {"json": lambda self: {"ok": True, "result": {"message_id": 7}}})()


@override_settings(TELEGRAM_BOT_TOKEN="bot-token", FRONTEND_URL="https://shop.example")
def test_telegram_publish_and_autopost(catalog, monkeypatch):
    fake = FakeTelegram()
    monkeypatch.setattr(tg.requests, "post", fake)
    product, *_ = catalog
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    url = reverse("marketing:telegram-publish", args=[product.pk])
    assert admin.post(url).status_code == 400  # канал не задан

    SiteSettings.objects.create(phone="1", telegram_channel="@my_shop_ua", telegram_autopost=True)
    resp = admin.post(url)
    assert resp.status_code == 200 and admin.get(url).json()["posted_at"]
    method, payload = fake.calls[-1]
    assert method == "sendMessage"  # у товара нет фото по https
    assert "Змішувач Grohe" in payload["text"] and "1 000 ₴" in payload["text"] and "<s>1 250 ₴</s>" in payload["text"]
    assert f"https://shop.example/product/{product.slug}" in payload["text"]

    # автопубликация: новый видимый товар через кабинет → один пост, повторно не публикуется
    new = admin.post(
        reverse("products:manage-product-list"),
        {"name": "Сифон", "variant": {"price": "300", "available": True}},
        format="json",
    ).json()
    assert TelegramPost.objects.filter(product_id=new["id"]).count() == 1
    admin.post(reverse("products:manage-product-bulk"), {"ids": [new["id"]], "action": "show"}, format="json")
    assert TelegramPost.objects.filter(product_id=new["id"]).count() == 1
    hidden = admin.post(
        reverse("products:manage-product-list"),
        {"name": "Прихований", "variant": {"price": "10", "available": False}},
        format="json",
    ).json()
    assert not TelegramPost.objects.filter(product_id=hidden["id"]).exists()
