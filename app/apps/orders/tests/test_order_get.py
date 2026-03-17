import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.orders.models import Order, Cart
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, OrderFactory
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory
from app.apps.accounts.tests.factories import UserFactory




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

@pytest.fixture
def another_user():
    return UserFactory()

@pytest.mark.django_db
def test_user_cannot_use_another_users_cart(api_client, user, django_user_model):
    # Создаем другого пользователя
    another_user = django_user_model.objects.create_user(email="other@example.com", password="password123")

    # Корзина другого пользователя
    foreign_cart = CartFactory(customer=another_user)
    CartItemsFactory(cart=foreign_cart, product=ProductFactory(), quantity=1)

    # Аутентифицируемся как user
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(foreign_cart.cart_uuid),
        "cart": foreign_cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555555",
        "address": "ул. Подмена, 1",
        "email": "test@test.com",
        "city": "ytn",
        "region": "yrtb",
        "department_number": "1",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400
    errors = response.json()
    assert "cart_uuid" in errors
    assert "Cart not found or already associated with an order" in str(errors["cart_uuid"])


@pytest.mark.django_db
def test_authenticated_user_can_create_order_with_own_cart(api_client, user):
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=2)
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555551",
        "address": "ул. Корзина, 1",
        "email": "test@test.com",
        "city": "dffd",
        "region": "dfdf",
        "department_number": "1",
    }

    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    data = response.json()
    order = Order.objects.get(id=data["id"])
    assert order.cart == cart
    assert order.customer == user
    assert order.customer_name == "Иван Иванов"


@pytest.mark.django_db
def test_order_list_returns_only_user_orders(api_client, user):
    other_user = UserFactory()
    # Создаем заказы для разных пользователей
    my_order = OrderFactory(customer=user)
    other_order = OrderFactory(customer=other_user)

    api_client.force_authenticate(user=user)
    url = reverse("orders:user-orders-list")  # URL для list action

    response = api_client.get(url)
    assert response.status_code == 200

    data = response.json()
    assert len(data) == 1
    assert data[0]['id'] == my_order.id


    order_data = data[0]
    assert 'list_of_product_images' in order_data
    assert 'number_products' in order_data
    assert 'status_order_display' in order_data
    assert 'payment_status_display' in order_data
