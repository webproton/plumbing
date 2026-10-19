"""Заказы в кабинете: доступ, фильтры, смена статуса со складом, оплата, заметка, смешанные заказы."""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.orders import services
from app.apps.orders.models import Order
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, stock_up
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory
from app.apps.warehouse.tests.factories import SellerFactory

pytestmark = pytest.mark.django_db
LIST = "orders:manage-order-list"


def _variant(seller=None, qty=10, price="100.00"):
    variant = ProductVariantFactory(product=ProductFactory(seller=seller), price=Decimal(price))
    stock_up(variant, qty)
    return ProductVariant.objects.get(pk=variant.pk)


def _order(*lines, name="Олена Коваль", phone="+380501234567"):
    cart = CartFactory()
    for variant, qty in lines:
        CartItemsFactory(cart=cart, product=variant.product, variant=variant, quantity=qty, stocked=0)
    data = {"customer_name": name, "phone_number": phone, "address": "Нова Пошта, Київ, 12", "email": "c@test.com"}
    return services.create_order_from_cart(cart, **data)


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def act(client, order, name, **data):
    return client.post(reverse(f"orders:manage-order-{name}", args=[order.pk]), data, format="json")


def test_admin_flow_with_stock(django_capture_on_commit_callbacks):
    admin = UserFactory(is_superuser=True)
    v = _variant(qty=5)
    order = _order((v, 2))
    c = _client(admin)

    rows = c.get(reverse(LIST), {"status": "in_processing"}).json()["results"]
    assert [r["id"] for r in rows] == [order.pk] and rows[0]["items_count"] == 1
    assert c.get(reverse(LIST), {"q": "0501234567"}).json()["count"] == 1
    assert c.get(reverse(LIST), {"q": f"#{order.pk}"}).json()["count"] == 1
    assert c.get(reverse(LIST), {"q": "Петро"}).json()["count"] == 0

    card = c.get(reverse("orders:manage-order-detail", args=[order.pk])).json()
    assert card["can_manage"] is True and [s["value"] for s in card["next_statuses"]][0] == "delivering"
    assert card["items"][0]["available_stock"] == "3.000"  # 5 − резерв 2

    assert act(c, order, "status", status="completed").status_code == 200
    v.refresh_from_db()
    assert (v.stock, v.reserved) == (Decimal("3.000"), Decimal("0.000"))  # списано со склада
    order.refresh_from_db()
    assert order.stock_state == "written_off" and order.manager == admin
    assert act(c, order, "status", status="canceled").status_code == 400  # из «завершён» переходов нет

    assert act(c, order, "payment", payment_status="paid_for").json()["payment_status"] == "paid_for"
    assert act(c, order, "payment", payment_status="bogus").status_code == 400
    assert (
        act(c, order, "note", manager_note="Передзвонити після 18:00").json()["manager_note"].startswith("Передзвонити")
    )
    assert c.get(reverse("orders:manage-order-counts")).json() == {"completed": 1}


def test_cancel_releases_reserve():
    admin = UserFactory(is_superuser=True)
    v = _variant(qty=5)
    order = _order((v, 3))
    assert act(_client(admin), order, "status", status="canceled").status_code == 200
    v.refresh_from_db()
    assert v.reserved == Decimal("0.000")


def test_seller_access_and_mixed_orders():
    seller = SellerFactory()
    other = SellerFactory()
    mine, theirs = _variant(seller), _variant(other)
    own_order = _order((mine, 1))
    mixed = _order((mine, 1), (theirs, 1))
    foreign = _order((theirs, 1))
    c = _client(seller.user)

    assert {r["id"] for r in c.get(reverse(LIST)).json()["results"]} == {own_order.pk, mixed.pk}
    assert c.get(reverse("orders:manage-order-detail", args=[foreign.pk])).status_code == 404
    assert c.get(reverse("orders:manage-order-detail", args=[mixed.pk])).json()["can_manage"] is False
    assert act(c, mixed, "status", status="canceled").status_code == 403
    assert act(c, own_order, "status", status="delivering").status_code == 200
    assert Order.objects.get(pk=mixed.pk).status_order == "in_processing"

    buyer = _client(UserFactory())
    assert buyer.get(reverse(LIST)).status_code == 403


def test_status_labels_follow_language():
    admin = UserFactory(is_superuser=True)
    order = _order((_variant(), 1))
    c = _client(admin)
    url = reverse("orders:manage-order-detail", args=[order.pk])
    uk = c.get(url, HTTP_ACCEPT_LANGUAGE="uk").json()
    assert (uk["status_display"], uk["payment_status_display"]) == ("В обробці", "Очікує оплати")
    assert uk["next_statuses"][0]["label"] == "Доставляється"
    ru = c.get(url, HTTP_ACCEPT_LANGUAGE="ru").json()
    assert ru["status_display"] == "В обработке"
