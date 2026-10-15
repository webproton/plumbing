import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.orders.models import Order
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, OrderFactory
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


@pytest.fixture
def another_user():
    return UserFactory()


@pytest.mark.django_db
def test_create_order_authenticated(api_client, user):
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=2)

    api_client.force_authenticate(user=user)
    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555555",
        "address": "ул. Тестовая, 1",
        "email": "ivan@test.com",
        "city": "Омск",
        "region": "Омская",
        "department_number": "1",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    assert Order.objects.count() == 1
    order = Order.objects.first()
    assert order.customer == user
    assert order.total_price > 0


@pytest.mark.django_db
def test_create_order_anonymous(api_client):
    cart = CartFactory(customer=None)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=1)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "Петр Петров",
        "phone_number": "+380987654321",
        "address": "ул. Анонимная, 2",
        "email": "anon@test.com",
        "city": "Львов",
        "region": "Львовская",
        "department_number": "2",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 201
    order = Order.objects.first()
    assert order.customer is None


@pytest.mark.django_db
def test_create_order_fails_if_cart_empty(api_client, user):
    cart = CartFactory(customer=user)  # без товаров
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555555",
        "address": "ул. Пустая, 3",
        "email": "test@test.com",
        "city": "Харьков",
        "region": "Харьковская",
        "department_number": "3",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400
    assert "Корзина пуста" in str(response.json())


@pytest.mark.django_db
def test_create_order_fails_if_order_already_exists(api_client, user):
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=1)
    api_client.force_authenticate(user=user)

    # первый заказ
    OrderFactory(cart=cart, customer=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555555",
        "address": "ул. Повторная, 4",
        "email": "test@test.com",
        "city": "нет",
        "region": "нет",
        "department_number": "4",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400

    errors = response.json()
    assert "cart_uuid" in errors
    assert "заказ по ней уже оформлен" in str(errors["cart_uuid"])


@pytest.mark.django_db
def test_create_order_fails_if_customer_name_missing(api_client, user):
    user.first_name = ""
    user.last_name = ""
    user.save()
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=1)
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "",  # пустое имя
        "phone_number": "+380505555555",
        "address": "ул. Безымянная, 5",
        "email": "test@test.com",
        "city": "несуществует",
        "region": "дно",
        "department_number": "5",
    }
    response = api_client.post(url, payload, format="json")

    # assert response.status_code == 400
    # assert "Укажите имя получателя" in str(response.json()['customer_name'])
    errors = response.json()
    assert "customer_name" in errors
    assert "Укажите имя получателя" in str(errors["customer_name"])


@pytest.mark.django_db
def test_create_order_fails_if_customer_name_invalid(api_client, user):
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=1)
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "123!@#",  # некорректное имя
        "phone_number": "+380505555555",
        "address": "ул. Некорректная, 6",
        "email": "test@test.com",
        "city": "Запорожье",
        "region": "Запорожская",
        "department_number": "6",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400
    assert "Имя может содержать только буквы" in str(response.json()["customer_name"])


@pytest.mark.django_db
def test_create_order_fails_if_comment_contains_link(api_client, user):
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=ProductFactory(), quantity=1)
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(cart.cart_uuid),
        "cart": cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555555",
        "address": "ул. Ссылочная, 7",
        "email": "test@test.com",
        "city": "Полтава",
        "region": "Полтавская",
        "department_number": "7",
        "comment": "посмотрите http://spam.com",
    }
    response = api_client.post(url, payload, format="json")

    assert response.status_code == 400
    assert "В комментарии не допускаются ссылки" in str(response.json())


@pytest.mark.django_db
def test_user_cannot_use_another_users_cart(api_client, user, another_user):
    # Создаем корзину другого пользователя
    foreign_cart = CartFactory(customer=another_user)
    CartItemsFactory(cart=foreign_cart, product=ProductFactory(), quantity=1)

    # Аутентификация как обычный пользователь
    api_client.force_authenticate(user=user)

    url = reverse("orders:order-create-list")
    payload = {
        "cart_uuid": str(foreign_cart.cart_uuid),  # пытаемся использовать чужую корзину
        "cart": foreign_cart.id,
        "customer_name": "Иван Иванов",
        "phone_number": "+380505555555",
        "address": "ул. Подмена, 1",
        "email": "test@test.com",
        "city": "Омск",
        "region": "Омская",
        "department_number": "1",
    }

    response = api_client.post(url, payload, format="json")

    # Проверяем, что заказ не создан
    assert response.status_code == 400

    errors = response.json()
    # В твоем validate нужно добавить проверку на принадлежность корзины пользователю
    # Тогда здесь можно ловить конкретную ошибку
    assert "cart" in errors or "cart_uuid" in errors
    assert "Корзина не найдена или заказ по ней уже оформлен" in str(errors.get("cart", errors.get("cart_uuid", "")))

    # И точно нет заказов на чужую корзину
    assert not Order.objects.filter(cart=foreign_cart).exists()
