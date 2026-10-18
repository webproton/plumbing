from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.orders.tests.factories import stock_up
from app.apps.products.models import Category, Product, ProductVariant

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


def _product(name, prices=(100,), available=True, category=None):
    product = Product.objects.create(name=name, category=category)
    for price in prices:
        ProductVariant.objects.create(product=product, price=Decimal(price), available=available)
    return product


def _results(resp):
    assert resp.status_code == 200, resp.content
    return resp.json()["results"]


def test_hidden_products_not_in_catalog(client):
    visible = _product("Смеситель")
    hidden = _product("Импорт из накладной", available=False)
    ids = {p["id"] for p in _results(client.get(reverse("products:product-list")))}
    assert visible.id in ids and hidden.id not in ids
    assert client.get(reverse("products:product-detail", args=[hidden.slug])).status_code == 404


def test_detail_shows_only_visible_variants(client):
    product = _product("Унитаз", prices=(100,))
    ProductVariant.objects.create(product=product, price=Decimal(50), available=False)
    data = client.get(reverse("products:product-detail", args=[product.slug])).json()
    assert len(data["variants"]) == 1


def test_list_price_is_min_of_visible_variants(client):
    product = _product("Ванна", prices=(300, 200))
    ProductVariant.objects.create(product=product, price=Decimal(10), available=False)
    item = next(p for p in _results(client.get(reverse("products:product-list"))) if p["id"] == product.id)
    assert Decimal(str(item["price"])) == Decimal("200")


def test_ordering_whitelist_and_unknown_value_ignored(client):
    _product("A", prices=(300,))
    _product("B", prices=(100,))
    names = [p["name"] for p in _results(client.get(reverse("products:product-list"), {"ordering": "-price"}))]
    assert names == ["A", "B"]
    # произвольное поле (например себестоимость) не принимается и не роняет запрос
    assert client.get(reverse("products:product-list"), {"ordering": "variants__cost_price"}).status_code == 200


def test_search_by_sku(client):
    product = _product("Сифон")
    variant = product.variants.get()
    ProductVariant.objects.filter(pk=variant.pk).update(code="SIF-777")
    names = [p["name"] for p in _results(client.get(reverse("products:product-list"), {"search": "sif-777"}))]
    assert names == ["Сифон"]


def test_variant_stock_flags(client):
    product = _product("Кран")
    variant = product.variants.get()
    data = client.get(reverse("products:product-detail", args=[product.slug])).json()
    assert data["variants"][0]["in_stock"] is False
    stock_up(variant, 3)
    data = client.get(reverse("products:product-detail", args=[product.slug])).json()
    assert data["variants"][0]["in_stock"] is True
    assert Decimal(data["variants"][0]["available_qty"]) == 3


def test_list_query_count_does_not_grow_with_products(client):
    cat = Category.objects.create(name="Смесители")
    for i in range(3):
        _product(f"P{i}", prices=(100, 200), category=cat)
    with CaptureQueriesContext(connection) as small:
        client.get(reverse("products:product-list"))
    for i in range(3, 15):
        _product(f"P{i}", prices=(100, 200), category=cat)
    with CaptureQueriesContext(connection) as big:
        client.get(reverse("products:product-list"))
    assert len(big) == len(small)


def test_cyrillic_category_gets_latin_slug_and_filters(client):
    a = Category.objects.create(name="Смесители")
    b = Category.objects.create(name="Змішувачі для кухні")
    c = Category.objects.create(name="Смесители")
    assert (a.slug, b.slug, c.slug) == ("smesiteli", "zmishuvachi-dlja-kuhni", "smesiteli-2")
    _product("Grohe", category=a)
    _product("Kran", category=b)
    names = [p["name"] for p in _results(client.get(reverse("products:product-list"), {"category": "smesiteli"}))]
    assert names == ["Grohe"]


def test_ukrainian_letters_transliterated_in_slugs():
    from app.apps.products.utils.slugs import make_slug

    assert make_slug("Змішувач їжак Євро ґанок") == "zmishuvach-yizhak-yevro-ganok"
