from io import StringIO

import pytest
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.products.catalog.services import ensure_taxonomy
from app.apps.products.catalog.taxonomy import VERTICALS
from app.apps.products.models import Product, ProductVariant
from app.apps.storefronts.models import Storefront
from app.apps.warehouse.tests.factories import SellerFactory

pytestmark = pytest.mark.django_db


def product(name, category, seller=None, price=100):
    item = Product.objects.create(name=name, category=category, seller=seller)
    ProductVariant.objects.create(product=item, price=price, available=True, variant_name=name)
    return item


@pytest.fixture
def catalog():
    bikes = ensure_taxonomy(VERTICALS["bikes"])
    tools = ensure_taxonomy(VERTICALS["tools"])
    return {
        "bike": product("Велосипед 29", bikes["velosypedy-dorosli"]),
        "chain": product("Ланцюг", bikes["velo-transmisiia"]),
        "drill": product("Шуруповерт", tools["dryli-shurupoverty"]),
    }


@pytest.fixture
def velo():
    return Storefront.objects.create(
        slug="velo", name="Вело", verticals=["bikes"], domains="velo-dnipro.com.ua\nveloshop.ua"
    )


def names(response):
    return sorted(p["name"] for p in response.json()["results"])


def test_general_shop_shows_everything(catalog):
    response = APIClient().get(reverse("products:product-list"))
    assert names(response) == ["Велосипед 29", "Ланцюг", "Шуруповерт"]


@pytest.mark.parametrize(
    "headers,query",
    [
        ({"HTTP_X_STOREFRONT": "velo"}, {}),
        ({}, {"storefront": "velo"}),
        ({"HTTP_X_STOREFRONT_HOST": "www.velo-dnipro.com.ua:443"}, {}),
        ({"HTTP_HOST": "veloshop.ua"}, {}),
    ],
)
def test_storefront_by_slug_query_or_domain(catalog, velo, headers, query, settings):
    settings.ALLOWED_HOSTS = ["*"]
    response = APIClient().get(reverse("products:product-list"), query, **headers)
    assert names(response) == ["Велосипед 29", "Ланцюг"]


def test_product_of_other_vertical_is_not_found_on_storefront(catalog, velo):
    client = APIClient()
    drill = reverse("products:product-detail", args=[catalog["drill"].slug])
    assert client.get(drill, HTTP_X_STOREFRONT="velo").status_code == 404
    assert client.get(drill).status_code == 200


def test_storefront_of_one_seller(catalog):
    shop = SellerFactory()
    tools = ensure_taxonomy(VERTICALS["tools"])
    product("Болгарка магазину", tools["bolharky-shlifmashyny"], seller=shop)
    storefront = Storefront.objects.create(slug="tools-shop", name="Інструмент", verticals=["tools"])
    storefront.sellers.add(shop)
    response = APIClient().get(reverse("products:product-list"), HTTP_X_STOREFRONT="tools-shop")
    assert names(response) == ["Болгарка магазину"]


def test_inactive_or_unknown_storefront_means_general_shop(catalog, velo):
    velo.is_active = False
    velo.save()
    client = APIClient()
    assert len(names(client.get(reverse("products:product-list"), HTTP_X_STOREFRONT="velo"))) == 3
    assert client.get(reverse("storefronts:current"), HTTP_X_STOREFRONT="nope").json() == {"storefront": None}


def test_category_filter_includes_subcategories(catalog):
    response = APIClient().get(reverse("products:product-list"), {"category": "velosypedy-i-sport"})
    assert names(response) == ["Велосипед 29", "Ланцюг"]


def test_categories_scoped_with_tree_fields(catalog, velo):
    client = APIClient()
    rows = client.get(reverse("products:category-list"), {"nonempty": "1"}, HTTP_X_STOREFRONT="velo").json()
    by_slug = {row["slug"]: row for row in rows}
    assert set(by_slug) == {
        "velosypedy-i-sport",
        "velosypedy",
        "velo-zapchastyny",
        "velosypedy-dorosli",
        "velo-transmisiia",
    }
    assert by_slug["velosypedy-i-sport"]["depth"] == 0
    assert by_slug["velo-zapchastyny"] == {**by_slug["velo-zapchastyny"], "parent": "velosypedy-i-sport", "depth": 1}
    assert by_slug["velo-transmisiia"]["depth"] == 2 and by_slug["velo-transmisiia"]["vertical"] == "bikes"
    # без nonempty — все категории направления (для редактора товаров)
    assert len(client.get(reverse("products:category-list"), HTTP_X_STOREFRONT="velo").json()) > len(rows)


def test_new_products_scoped(catalog, velo):
    rows = APIClient().get(reverse("products:new-products-list"), HTTP_X_STOREFRONT="velo").json()
    assert sorted(p["name"] for p in rows) == ["Велосипед 29", "Ланцюг"]


def test_current_and_demo_endpoints(velo):
    velo.is_demo = True
    velo.brand_color = "#15803d"
    velo.save()
    client = APIClient()
    data = client.get(reverse("storefronts:current"), HTTP_X_STOREFRONT="velo").json()["storefront"]
    assert (data["name"], data["verticals"], data["brand_color"]) == ("Вело", ["bikes"], "#15803d")
    assert client.get(reverse("storefronts:current")).json() == {"storefront": None}
    assert [s["slug"] for s in client.get(reverse("storefronts:demo")).json()] == ["velo"]


def test_seed_storefronts_with_products():
    SellerFactory()
    call_command("seed_storefronts", "--products", "--force", stdout=StringIO())
    call_command("seed_storefronts", "--products", "--force", stdout=StringIO())  # повторный запуск без дублей
    assert set(Storefront.objects.values_list("slug", flat=True)) == {"velo", "instrument", "santekhnika"}
    client = APIClient()
    velo = names(client.get(reverse("products:product-list"), {"page_size": 100}, HTTP_X_STOREFRONT="velo"))
    tools = names(client.get(reverse("products:product-list"), {"page_size": 100}, HTTP_X_STOREFRONT="instrument"))
    assert len(velo) == 15 and len(tools) == 12
    assert "Шуруповерт" not in " ".join(velo)
