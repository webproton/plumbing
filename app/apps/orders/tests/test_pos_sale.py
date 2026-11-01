"""Касса на точке: продажа «человеку с улицы» из кабинета продавца — без покупателя, оплачено, списано сразу."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.orders.models import Order
from app.apps.orders.tests.factories import stock_up
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory
from app.apps.warehouse.tests.factories import SellerFactory

pytestmark = pytest.mark.django_db
SALE = "orders:manage-order-pos-sale"


def _variant(seller, qty=5, price="100.00", name="Змішувач Grohe"):
    variant = ProductVariantFactory(product=ProductFactory(seller=seller, name=name), price=Decimal(price))
    if qty:
        stock_up(variant, qty)
    return ProductVariant.objects.get(pk=variant.pk)


def _client(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def test_sale_is_paid_completed_and_written_off(django_capture_on_commit_callbacks):
    seller = SellerFactory()
    tap = _variant(seller, qty=5)
    client = _client(seller.user)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = client.post(reverse(SALE), {
            "lines": [{"variant": tap.pk, "quantity": 1}, {"variant": tap.pk, "quantity": 1}],
            "payment_method": "cash", "discount_percent": 5,
        }, format="json")
    assert response.status_code == 200, response.content
    data = response.json()
    assert (data["channel"], data["payment_method"], data["discount_percent"]) == ("pos", "cash", 5)
    assert data["channel_display"] == "На місці" and data["payment_method_display"] == "Готівка"
    assert data["total_price"] == "190.00" and data["items"][0]["unit_price"] == "95.00"  # 2 × 100 − 5 %

    order = Order.objects.get(pk=data["id"])
    assert order.customer is None and order.customer_name == "Покупець на місці"
    assert (order.status_order, order.payment_status, order.stock_state) == ("completed", "paid_for", "written_off")
    assert order.manager == seller.user
    tap.refresh_from_db()
    assert (tap.stock, tap.reserved) == (Decimal("3.000"), Decimal("0.000"))  # списано сразу, без резерва
    assert not callbacks  # ни письма, ни «новый заказ» в Telegram — покупатель уже ушёл с товаром

    rows = client.get(reverse("orders:manage-order-list"), {"channel": "pos"}).json()["results"]
    assert [r["id"] for r in rows] == [order.pk]
    assert client.get(reverse("orders:manage-order-list"), {"channel": "site"}).json()["count"] == 0
    stats = client.get(reverse("orders:manage-order-stats"), {"days": 30}).json()
    assert stats["by_channel"] == [{"channel": "pos", "label": "На місці", "revenue": 190.0, "orders": 1}]


def test_iban_and_card_without_discount():
    seller = SellerFactory()
    tap = _variant(seller)
    for method in ("card", "iban"):
        data = _client(seller.user).post(reverse(SALE), {"lines": [{"variant": tap.pk, "quantity": 1}],
                                                         "payment_method": method}, format="json").json()
        assert (data["payment_method"], data["total_price"], data["discount_percent"]) == (method, "100.00", 0)
    assert Order.objects.get(payment_method="iban").get_payment_method_display() == "Переказ на рахунок ФОП"


def test_not_enough_stock_and_bad_input_sell_nothing():
    seller = SellerFactory()
    tap = _variant(seller, qty=1, name="Сифон")
    foreign = _variant(SellerFactory(), qty=5)
    client = _client(seller.user)

    def sell(**data):
        return client.post(reverse(SALE), {"payment_method": "cash", **data}, format="json")

    short = sell(lines=[{"variant": tap.pk, "quantity": 3}])
    assert short.status_code == 400
    assert "Сифон" in str(short.json()) and "Перерахунок" in str(short.json())
    assert sell(lines=[{"variant": foreign.pk, "quantity": 1}]).status_code == 400  # чужой товар не продать
    assert sell(lines=[]).status_code == 400
    assert sell(lines=[{"variant": tap.pk, "quantity": 0}]).status_code == 400
    assert sell(lines=[{"variant": tap.pk, "quantity": 1}], discount_percent=7).status_code == 400  # скидка 0–5 %
    assert client.post(reverse(SALE), {"lines": [{"variant": tap.pk, "quantity": 1}], "payment_method": "barter"},
                       format="json").status_code == 400
    assert not Order.objects.exists()
    tap.refresh_from_db()
    assert (tap.stock, tap.reserved) == (Decimal("1.000"), Decimal("0.000"))

    assert _client(UserFactory()).post(reverse(SALE), {}, format="json").status_code == 403  # покупатель — не касса
