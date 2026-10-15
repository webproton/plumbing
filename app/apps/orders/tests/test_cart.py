import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def product():
    return ProductFactory()


@pytest.fixture
def product_variant(product):
    return ProductVariantFactory(product=product)


@pytest.mark.django_db(transaction=True)(transaction=True)
def test_create_cart_authenticated(api_client, user, product_variant):
    api_client.force_authenticate(user=user)
    url = reverse("orders:cart-list")
    payload = {"cart_items": [{"product": product_variant.product.id, "variant": product_variant.id, "quantity": 2}]}
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 201
    data = response.json()
    assert "id" in data
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["quantity"] == 2


@pytest.mark.django_db(transaction=True)
def test_create_cart_anonymous(api_client, product_variant):
    url = reverse("orders:cart-list")
    payload = {
        "cart_items": [{"product": product_variant.product.id, "variant": product_variant.id, "quantity": 1}]
        # 👇 без cart_uuid — сервер должен сам сгенерировать
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    data = response.json()

    # Проверяем, что корзина создана
    assert "cart_uuid" in data
    assert data["cart_items"][0]["product"] == product_variant.product.id
    assert data["cart_items"][0]["variant"] == product_variant.id
    assert data["cart_items"][0]["quantity"] == 1


@pytest.mark.django_db(transaction=True)(transaction=True)
def test_create_cart_empty_items(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("orders:cart-list")
    payload = {"cart_items": []}
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 400
    assert "Cart items cannot be empty." in response.json()["cart_items"][0]


@pytest.mark.django_db(transaction=True)(transaction=True)
def test_cart_item_validation_invalid_variant(api_client, user, product):
    api_client.force_authenticate(user=user)
    url = reverse("orders:cart-list")
    payload = {"cart_items": [{"product": product.id, "variant": 9999, "quantity": 1}]}
    response = api_client.post(url, payload, format="json")
    assert response.status_code == 400
    errors = response.json()["cart_items"][0]["variant"][0]
    assert "does not exist" in errors


@pytest.mark.django_db(transaction=True)
def test_cart_update_quantity(api_client, user, product_variant):
    api_client.force_authenticate(user=user)
    cart = CartFactory(customer=user)
    item = CartItemsFactory(cart=cart, product=product_variant.product, variant=product_variant, quantity=1)
    url = reverse("orders:cart-detail", args=[cart.id])
    payload = {"cart_items": [{"product": product_variant.product.id, "variant": product_variant.id, "quantity": 5}]}
    response = api_client.put(url, payload, format="json")
    assert response.status_code == 200
    item.refresh_from_db()
    assert item.quantity == 5


@pytest.mark.django_db(transaction=True)
def test_get_cart_by_uuid(api_client, product_variant):
    cart = CartFactory(cart_uuid="22222222-2222-2222-2222-222222222222", customer=None)
    CartItemsFactory(cart=cart, product=product_variant.product, variant=product_variant, quantity=1)
    url = reverse("orders:cart-get-by-uuid")
    response = api_client.get(url, {"cart_uuid": "22222222-2222-2222-2222-222222222222"})
    assert response.status_code == 200
    data = response.json()
    assert data["cart_uuid"] == "22222222-2222-2222-2222-222222222222"
    assert len(data["cart_items"]) == 1


@pytest.mark.django_db(transaction=True)
def test_cart_owner_access(api_client, user, product_variant):
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=product_variant.product, variant=product_variant, quantity=3)
    api_client.force_authenticate(user=user)

    url = reverse("orders:cart-detail", args=[cart.id])
    response = api_client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == cart.id
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["quantity"] == 3


@pytest.mark.django_db(transaction=True)
def test_cart_access_denied_for_other_user(api_client, user):
    other_user = UserFactory()
    cart = CartFactory(customer=other_user)
    api_client.force_authenticate(user=user)

    url = reverse("orders:cart-detail", args=[cart.id])
    response = api_client.get(url)
    assert response.status_code == 404


@pytest.mark.django_db(transaction=True)
def test_cart_access_by_uuid_anonymous(api_client, product_variant):
    cart_uuid = "33333333-3333-3333-3333-333333333333"
    cart = CartFactory(customer=None, cart_uuid=cart_uuid)
    CartItemsFactory(cart=cart, product=product_variant.product, variant=product_variant, quantity=2)

    url = reverse("orders:cart-get-by-uuid")
    response = api_client.get(url, {"cart_uuid": cart_uuid})
    assert response.status_code == 200
    data = response.json()
    assert data["cart_uuid"] == cart_uuid
    assert len(data["cart_items"]) == 1
    assert data["cart_items"][0]["quantity"] == 2


@pytest.mark.django_db(transaction=True)
def test_cart_access_denied_wrong_uuid(api_client):
    cart_uuid = "44444444-4444-4444-4444-444444444444"
    CartFactory(customer=None, cart_uuid=cart_uuid)

    url = reverse("orders:cart-get-by-uuid")
    response = api_client.get(url, {"cart_uuid": "55555555-5555-5555-5555-555555555555"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Cart not found"


@pytest.mark.django_db(transaction=True)
def test_cart_update_permission_denied(api_client, user):
    other_user = UserFactory()
    cart = CartFactory(customer=other_user)
    api_client.force_authenticate(user=user)
    url = reverse("orders:cart-detail", args=[cart.id])
    payload = {"cart_items": [{"product": ProductFactory().id, "quantity": 1, "variant": None}]}
    response = api_client.put(url, payload, format="json")
    assert response.status_code == 404
