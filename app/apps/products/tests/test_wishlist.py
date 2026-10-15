import pytest
from rest_framework.test import APIClient
from app.apps.accounts.tests.factories import UserFactory
from .factories import ProductVariantFactory
from app.apps.products.models import Wishlist

pytestmark = pytest.mark.django_db

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def user():
    return UserFactory()

@pytest.fixture
def variant():
    return ProductVariantFactory()

def test_wishlist_list_authenticated(api_client, user, variant):
    api_client.force_authenticate(user=user)
    # создаём wishlist
    Wishlist.objects.create(user=user, product_variant=variant)
    response = api_client.get("/api/wishlist/")
    assert response.status_code == 200
    assert len(response.data) == 1

def test_wishlist_create_authenticated(api_client, user, variant):
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/wishlist/", {"product_variant_id": variant.id})
    assert response.status_code == 201
    assert Wishlist.objects.filter(user=user, product_variant=variant).exists()

def test_wishlist_create_anonymous(api_client, variant):
    response = api_client.post("/api/wishlist/", {"product_variant_id": variant.id})
    assert response.status_code == 401

def test_wishlist_create_variant_not_exist(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/wishlist/", {"product_variant_id": 99999})
    assert response.status_code == 404

def test_wishlist_create_no_variant_id(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.post("/api/wishlist/", {})
    assert response.status_code == 400

def test_wishlist_bulk_update_empty_list(api_client, user):
    api_client.force_authenticate(user=user)
    response = api_client.put(
        "/api/wishlist/bulk-update/",
        data=[],             # передаем пустой список
        format='json'        # важно! чтобы DRF понимал, что это JSON
    )
    assert response.status_code == 200
    assert response.data == []  # если bulk_update возвращает пустой список

def test_wishlist_clear(api_client, user, variant):
    api_client.force_authenticate(user=user)
    Wishlist.objects.create(user=user, product_variant=variant)
    response = api_client.post("/api/wishlist/clear/")
    assert response.status_code == 200
    assert Wishlist.objects.filter(user=user).count() == 0
