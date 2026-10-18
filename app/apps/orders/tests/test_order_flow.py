import threading
from decimal import Decimal

import pytest
from django.core import mail
from django.db import connection
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.orders import services
from app.apps.orders.models import Cart, Order
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, OrderFactory, stock_up
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory
from app.apps.warehouse import stock

ORDER_URL = "orders:order-create-list"


def _payload(cart_obj, **extra):
    data = {
        "cart_uuid": str(cart_obj.cart_uuid),
        "customer_name": "Мар'яна Коваль-Петренко",
        "phone_number": "0501234567",
        "address": "вул. Тестова, 1",
        "email": "client@test.com",
        "city": "Київ",
        "department_number": "12",
    }
    data.update(extra)
    return data


def _variant(price="100.00", stock_qty=10):
    variant = ProductVariantFactory(product=ProductFactory(), price=Decimal(price))
    if stock_qty:
        stock_up(variant, stock_qty)
    return ProductVariant.objects.get(pk=variant.pk)


def _cart(user=None, items=()):
    cart = CartFactory(customer=user)
    for variant, qty in items:
        CartItemsFactory(cart=cart, product=variant.product, variant=variant, quantity=qty, stocked=0)
    return cart


@pytest.fixture
def client():
    return APIClient()


# --- оформление и резерв -------------------------------------------------


@pytest.mark.django_db
def test_order_reserves_stock_and_snapshots_price(client, django_capture_on_commit_callbacks):
    variant = _variant(price="250.00", stock_qty=5)
    cart = _cart(items=[(variant, 2)])

    with django_capture_on_commit_callbacks(execute=True):
        resp = client.post(reverse(ORDER_URL), _payload(cart), format="json")
    assert resp.status_code == 201, resp.json()

    order = Order.objects.get(pk=resp.json()["id"])
    assert order.stock_state == Order.STOCK_STATE.reserved
    assert order.total_price == Decimal("500.00")
    assert order.phone_number == "+380501234567"
    v = ProductVariant.objects.get(pk=variant.pk)
    assert (v.stock, v.reserved, v.available_stock) == (5, 2, 3)

    # цена в заказе не меняется при изменении цены товара
    ProductVariant.objects.filter(pk=variant.pk).update(price=Decimal("999.00"))
    item = order.items.get()
    assert item.unit_price == Decimal("250.00") and item.line_total == Decimal("500.00")

    # письмо клиенту отправлено после коммита
    assert len(mail.outbox) == 1 and f"№{order.pk}" in mail.outbox[0].subject


@pytest.mark.django_db
def test_order_rejected_when_not_enough_stock(client):
    variant = _variant(stock_qty=1)
    cart = _cart(items=[(variant, 2)])
    resp = client.post(reverse(ORDER_URL), _payload(cart), format="json")
    assert resp.status_code == 400
    assert resp.json()["code"] == "insufficient_stock"
    assert not Order.objects.exists()
    assert ProductVariant.objects.get(pk=variant.pk).reserved == 0


@pytest.mark.django_db
def test_reserved_stock_is_not_sold_twice(client):
    variant = _variant(stock_qty=3)
    first = client.post(reverse(ORDER_URL), _payload(_cart(items=[(variant, 2)])), format="json")
    second = client.post(reverse(ORDER_URL), _payload(_cart(items=[(variant, 2)])), format="json")
    assert first.status_code == 201
    assert second.status_code == 400


# --- статусы ------------------------------------------------------------


@pytest.mark.django_db
def test_customer_cancel_releases_reserve(client):
    user = UserFactory()
    variant = _variant(stock_qty=5)
    cart = _cart(user=user, items=[(variant, 3)])
    client.force_authenticate(user)
    order_id = client.post(reverse(ORDER_URL), _payload(cart), format="json").json()["id"]

    resp = client.post(reverse("orders:user-orders-cancel", args=[order_id]))
    assert resp.status_code == 200
    order = Order.objects.get(pk=order_id)
    assert order.status_order == Order.STATUS.canceled
    assert order.stock_state == Order.STOCK_STATE.released
    assert ProductVariant.objects.get(pk=variant.pk).reserved == 0


@pytest.mark.django_db
def test_completion_writes_off_and_blocks_cancel(client):
    variant = _variant(stock_qty=5)
    order_id = client.post(reverse(ORDER_URL), _payload(_cart(items=[(variant, 2)])), format="json").json()["id"]
    order = Order.objects.get(pk=order_id)

    services.change_status(order, Order.STATUS.completed)
    order.refresh_from_db()
    v = ProductVariant.objects.get(pk=variant.pk)
    assert order.stock_state == Order.STOCK_STATE.written_off
    assert (v.stock, v.reserved) == (3, 0)
    assert stock.journal_balance(variant.pk) == 3

    with pytest.raises(ValidationError):
        services.change_status(order, Order.STATUS.canceled)


@pytest.mark.django_db
def test_legacy_order_completion_keeps_other_reservations(client):
    variant = _variant(stock_qty=5)
    # новый заказ резервирует 2
    client.post(reverse(ORDER_URL), _payload(_cart(items=[(variant, 2)])), format="json")
    # старый заказ (до резервов) на 1 шт.
    legacy = OrderFactory(customer=None, stock_state=Order.STOCK_STATE.none)
    legacy.items.create(variant=variant, product=variant.product, name="x", unit_price=1, quantity=1)

    services.change_status(legacy, Order.STATUS.completed)
    v = ProductVariant.objects.get(pk=variant.pk)
    assert (v.stock, v.reserved) == (4, 2)  # резерв нового заказа не тронут


# --- корзина ------------------------------------------------------------


@pytest.mark.django_db
def test_cart_sync_replaces_quantities(client):
    a, b = _variant(), _variant()
    url = reverse("orders:cart-list")
    items = [
        {"product": a.product_id, "variant": a.pk, "quantity": 2},
        {"product": b.product_id, "variant": b.pk, "quantity": 1},
    ]
    first = client.post(url, {"cart_items": items}, format="json").json()
    cart_uuid = first["cart_uuid"]

    # повторная синхронизация той же корзины не удваивает количества
    again = client.post(url, {"cart_items": items, "cart_uuid": cart_uuid}, format="json").json()
    assert sorted(i["quantity"] for i in again["cart_items"]) == [1, 2]

    # позиция, которой нет в запросе, удаляется
    only_a = client.post(url, {"cart_items": items[:1], "cart_uuid": cart_uuid}, format="json").json()
    assert [(i["variant"], i["quantity"]) for i in only_a["cart_items"]] == [(a.pk, 2)]
    assert Cart.objects.count() == 1


@pytest.mark.django_db
def test_cart_item_reports_price_of_selected_variant(client):
    product = ProductFactory()
    ProductVariantFactory(product=product, price=Decimal("10"))
    expensive = ProductVariantFactory(product=product, price=Decimal("500"))
    resp = client.post(
        reverse("orders:cart-list"),
        {"cart_items": [{"product": product.pk, "variant": expensive.pk, "quantity": 1}]},
        format="json",
    )
    assert Decimal(resp.json()["cart_items"][0]["price"]) == Decimal("500")


@pytest.mark.django_db
def test_anonymous_can_open_own_cart_by_uuid(client):
    cart = _cart(items=[(_variant(), 1)])
    resp = client.get(reverse("orders:cart-detail", args=[cart.pk]), {"cart_uuid": str(cart.cart_uuid)})
    assert resp.status_code == 200


@pytest.mark.django_db
def test_cart_pk_in_payload_cannot_hijack_foreign_cart(client):
    victim_cart = _cart(user=UserFactory(), items=[(_variant(), 1)])
    my_cart = _cart(items=[(_variant(), 1)])
    resp = client.post(reverse(ORDER_URL), _payload(my_cart, cart=victim_cart.pk), format="json")
    assert resp.status_code == 201
    assert Order.objects.get().cart_id == my_cart.pk
    assert not Order.objects.filter(cart=victim_cart).exists()


@pytest.mark.django_db
def test_order_history_requires_auth(client):
    assert client.get(reverse("orders:user-orders-list")).status_code in (401, 403)


# --- гонки --------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_double_submit_creates_single_order():
    variant = _variant(stock_qty=10)
    cart = _cart(items=[(variant, 1)])
    barrier, codes = threading.Barrier(5), []

    def submit():
        try:
            barrier.wait()
            codes.append(APIClient().post(reverse(ORDER_URL), _payload(cart), format="json").status_code)
        finally:
            connection.close()

    threads = [threading.Thread(target=submit) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert codes.count(201) == 1
    assert Order.objects.filter(cart=cart).count() == 1
    assert ProductVariant.objects.get(pk=variant.pk).reserved == 1


@pytest.mark.django_db
def test_current_cart_for_guest_and_claim_after_login(client):
    variant = _variant()
    url = reverse("orders:cart-current")
    assert client.get(url).status_code == 204
    created = client.post(
        reverse("orders:cart-list"),
        {"cart_items": [{"product": variant.product_id, "variant": variant.pk, "quantity": 2}]},
        format="json",
    ).json()
    guest = client.get(url, {"cart_uuid": created["cart_uuid"]})
    assert guest.status_code == 200 and guest.json()["cart_items"][0]["quantity"] == 2

    user = UserFactory()
    client.force_authenticate(user)
    claimed = client.get(url, {"cart_uuid": created["cart_uuid"]})
    assert claimed.status_code == 200 and claimed.json()["customer"] == user.pk


@pytest.mark.django_db
def test_api_messages_follow_accept_language(client, settings):
    settings.LANGUAGE_CODE = "uk"
    cart = CartFactory(customer=None)  # пустая корзина
    url = reverse(ORDER_URL)
    uk = client.post(url, _payload(cart), format="json", HTTP_ACCEPT_LANGUAGE="uk-UA")
    ru = client.post(url, _payload(cart), format="json", HTTP_ACCEPT_LANGUAGE="ru-UA")
    assert "Кошик порожній" in str(uk.json())
    assert "Корзина пуста" in str(ru.json())
    bad_phone = client.post(
        url, _payload(cart, phone_number="+7 (999) 123 45 67"), format="json", HTTP_ACCEPT_LANGUAGE="uk"
    )
    assert "+380" in str(bad_phone.json()["phone_number"])


@pytest.mark.django_db
def test_formatted_ukrainian_phone_is_accepted_and_normalized(client):
    variant = _variant()
    cart = _cart(items=[(variant, 1)])
    resp = client.post(reverse(ORDER_URL), _payload(cart, phone_number="+38 (050) 123-45-67"), format="json")
    assert resp.status_code == 201, resp.json()
    assert Order.objects.get().phone_number == "+380501234567"
