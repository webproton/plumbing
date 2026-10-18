from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def wh(seller):
    return WarehouseFactory(seller=seller, is_default=True)


@pytest.fixture
def client(seller):
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


def _stocked(wh, qty, **fields):
    variant = ProductVariantFactory(cost_price=Decimal("10.00"), **fields)
    stock.receive(variant, wh, qty, supplier=SupplierFactory())
    return variant


def test_me_for_roles(seller, wh):
    c = APIClient()
    c.force_authenticate(seller.user)
    data = c.get(reverse("warehouse:me")).json()
    assert data["is_staff_user"] is True
    assert data["seller"]["shop_name"] == seller.shop_name
    assert [w["id"] for w in data["warehouses"]] == [wh.pk]

    plain = APIClient()
    plain.force_authenticate(UserFactory())
    assert plain.get(reverse("warehouse:me")).json()["is_staff_user"] is False

    pending = SellerFactory(is_approved=False)
    c2 = APIClient()
    c2.force_authenticate(pending.user)
    info = c2.get(reverse("warehouse:me")).json()
    assert info["is_staff_user"] is False and info["seller_pending"] is True

    assert APIClient().get(reverse("warehouse:me")).status_code in (401, 403)


def test_balances_list_search_and_isolation(client, wh):
    a = _stocked(wh, 5, variant_name="Змішувач Grohe", code="GR-1", barcode="4820000000011")
    _stocked(wh, 2, variant_name="Кран шаровий")
    foreign = WarehouseFactory()  # чужой склад
    stock.receive(ProductVariantFactory(variant_name="Чужой товар"), foreign, 9, supplier=SupplierFactory())

    resp = client.get(reverse("warehouse:balances-list"))
    names = [r["variant_name"] for r in resp.json()["results"]]
    assert resp.json()["count"] == 2 and "Чужой товар" not in names

    by_code = client.get(reverse("warehouse:balances-list"), {"search": "gr-1"}).json()["results"]
    assert [r["variant"] for r in by_code] == [a.pk]
    by_barcode = client.get(reverse("warehouse:balances-list"), {"search": "4820000000011"}).json()["results"]
    assert by_barcode[0]["value"] == "50.00"  # 5 × 10.00 по себестоимости

    assert client.get(reverse("warehouse:balances-list"), {"warehouse": foreign.pk}).json()["count"] == 0


def test_movements_paginated_with_search(client, wh):
    v = _stocked(wh, 1, variant_name="Сифон")
    for _ in range(30):
        stock.receive(v, wh, 1, supplier=SupplierFactory())
    page = client.get(reverse("warehouse:stock-movements-list")).json()
    assert page["count"] == 31 and len(page["results"]) == 25 and page["next"]
    found = client.get(reverse("warehouse:stock-movements-list"), {"search": "Сифон", "page_size": 5}).json()
    assert len(found["results"]) == 5


def test_variant_search_and_dashboard(client, wh):
    v = _stocked(wh, 4, variant_name="Труба PPR 20", code="PPR-20")
    found = client.get(reverse("warehouse:variant_search"), {"q": "ppr-20"}).json()
    assert found[0]["id"] == v.pk and Decimal(found[0]["available"]) == 4

    dash = client.get(reverse("warehouse:dashboard")).json()
    assert dash["positions"] == 1 and Decimal(str(dash["units"])) == 4 and Decimal(str(dash["value"])) == 40
    assert dash["recent_movements"][0]["variant_name"] == "Труба PPR 20"
    assert dash["documents_pending"] == 0


def test_cabinet_requires_staff():
    c = APIClient()
    c.force_authenticate(UserFactory())
    for name in ("warehouse:dashboard", "warehouse:balances-list", "warehouse:variant_search"):
        assert c.get(reverse(name)).status_code == 403
