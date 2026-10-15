import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.products.models import Category, Product, ProductVariant

pytestmark = pytest.mark.django_db

photo_file = SimpleUploadedFile(
    name="test.jpg",
    content=b"",  # можно оставить пустое содержимое
    content_type="image/jpeg",
)


# -----------------------------
# Category tests
# -----------------------------
def test_category_list(client: APIClient):
    cat = Category.objects.create(name="Category 1")
    url = reverse("products:category-list")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()
    assert any(item["id"] == cat.id for item in data)


def test_category_detail(client: APIClient):
    cat = Category.objects.create(name="Category 2")
    url = reverse("products:category-detail", args=[cat.slug])
    response = client.get(url)
    assert response.status_code == 200
    assert response.json()["id"] == cat.id


# -----------------------------
# Product list and detail tests
# -----------------------------
@pytest.mark.django_db
def test_product_list_and_detail(client: APIClient):
    category = Category.objects.create(name="Cat 1")
    product = Product.objects.create(name="Prod 1", category=category)
    variant = ProductVariant.objects.create(product=product, price=100)

    # Список продуктов
    url = reverse("products:product-list")
    response = client.get(url)
    assert response.status_code == 200
    data = response.json()["results"]
    assert any(p["id"] == product.id for p in data)

    # Детали продукта
    url_detail = reverse("products:product-detail", args=[product.slug])
    response = client.get(url_detail)
    assert response.status_code == 200
    detail_data = response.json()
    assert detail_data["id"] == product.id
    assert "variants" in detail_data
    assert len(detail_data["variants"]) == 1
    assert detail_data["variants"][0]["id"] == variant.id


# -----------------------------
# Product filtering / search tests
# -----------------------------
def test_product_filter_by_category(client: APIClient):
    cat1 = Category.objects.create(name="C1")
    cat2 = Category.objects.create(name="C2")
    prod1 = Product.objects.create(name="P1", category=cat1)
    prod2 = Product.objects.create(name="P2", category=cat2)
    ProductVariant.objects.create(product=prod1, price=50)
    ProductVariant.objects.create(product=prod2, price=100)

    url = reverse("products:product-list")
    response = client.get(url, {"category": cat1.slug})
    data = response.json()["results"]
    assert len(data) == 1
    assert data[0]["id"] == prod1.id


def test_product_search(client: APIClient):
    cat = Category.objects.create(name="C1")
    prod1 = Product.objects.create(name="Alpha", category=cat)
    prod2 = Product.objects.create(name="Beta", category=cat)
    ProductVariant.objects.create(product=prod1, price=50)
    ProductVariant.objects.create(product=prod2, price=100)

    url = reverse("products:product-list")
    response = client.get(url, {"search": "Alpha"})
    data = response.json()["results"]
    assert len(data) == 1
    assert data[0]["name"] == "Alpha"
