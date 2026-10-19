"""Редактор товаров кабинета: права, список, создание/правка, варианты, фото, массовые действия, удаление."""

from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.products.models import Brand, Product, ProductVariant
from app.apps.products.tests.factories import CategoryFactory, ProductFactory, ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db
LIST = "products:manage-product-list"


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def client(seller):
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


def png(name="p.png", color="red"):
    buf = BytesIO()
    Image.new("RGB", (20, 20), color).save(buf, "PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


def detail(pk):
    return reverse("products:manage-product-detail", args=[pk])


def test_access_and_isolation(client, seller):
    mine = ProductVariantFactory(product__seller=seller).product
    other = ProductVariantFactory(product__seller=SellerFactory()).product
    ids = [p["id"] for p in client.get(reverse(LIST)).json()["results"]]
    assert ids == [mine.pk]
    assert client.get(detail(other.pk)).status_code == 404

    buyer = APIClient()
    buyer.force_authenticate(UserFactory())
    assert buyer.get(reverse(LIST)).status_code == 403

    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    assert {p["id"] for p in admin.get(reverse(LIST)).json()["results"]} >= {mine.pk, other.pk}


def test_list_annotations_and_filters(client, seller):
    wh = WarehouseFactory(seller=seller)
    product = ProductFactory(seller=seller, name="Змішувач Grohe", photo="")
    a = ProductVariantFactory(product=product, code="GR-1", price=Decimal("200"), available=False)
    b = ProductVariantFactory(product=product, code="GR-2", price=Decimal("150"), available=True)
    stock.receive(a, wh, 5, supplier=SupplierFactory())
    stock.receive(b, wh, 3, supplier=SupplierFactory())
    hidden = ProductVariantFactory(product__seller=seller, product__name="Сифон", available=False).product

    row = client.get(reverse(LIST), {"q": "GR-"}).json()["results"]
    assert len(row) == 1
    row = row[0]
    assert (row["variants_count"], row["price_min"], row["stock"], row["visible"]) == (2, "150.00", "8.000", True)
    assert [p["id"] for p in client.get(reverse(LIST), {"visible": "0"}).json()["results"]] == [hidden.pk]
    assert [p["id"] for p in client.get(reverse(LIST), {"in_stock": "1"}).json()["results"]] == [product.pk]


def test_create_update_and_variants(client, seller):
    category = CategoryFactory()
    resp = client.post(
        reverse(LIST),
        {
            "name": "Бойлер 80 л",
            "category": category.pk,
            "description": "Електричний",
            "variant": {
                "code": "BL-80",
                "price": "5999",
                "old_price": "6999",
                "cost_price": "4200",
                "available": False,
                "brand_name": "Ariston",
            },
        },
        format="json",
    )
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    (v,) = data["variants"]
    assert (v["code"], v["price"], v["original_price_value"], v["discount"], v["available"], v["brand"]) == (
        "BL-80", "5999.0000", "6999.0000", 14, False, "Ariston",
    )  # fmt: skip
    product = Product.objects.get(pk=data["id"])
    assert product.seller == seller and product.slug

    dup = client.post(reverse(LIST), {"name": "Інший", "variant": {"code": "bl-80", "price": "1"}}, format="json")
    assert dup.status_code == 400
    assert client.post(reverse(LIST), {"name": "Без ціни"}, format="json").status_code == 400

    assert client.patch(detail(product.pk), {"name": "Бойлер 80 л вертикальний"}, format="json").status_code == 200
    resp = client.post(
        reverse("products:manage-product-variants", args=[product.pk]),
        {"variant_name": "100 л", "price": "6500"},
        format="json",
    )
    assert resp.status_code == 201 and len(resp.json()["variants"]) == 2
    new_variant = ProductVariant.objects.get(product=product, variant_name="100 л")
    assert new_variant.code and new_variant.barcode  # сгенерированы

    vurl = reverse("products:manage-variant-detail", args=[new_variant.pk])
    assert client.patch(vurl, {"price": "7000", "old_price": "6000"}, format="json").status_code == 400
    resp = client.patch(vurl, {"price": "7000", "old_price": None, "available": True}, format="json")
    assert resp.status_code == 200 and resp.json()["discount"] == 0 and resp.json()["available"] is True
    assert Brand.objects.filter(name="Ariston").count() == 1


def test_photos(client, seller):
    product = ProductVariantFactory(product__seller=seller, product__photo="").product
    url = reverse("products:manage-product-photos", args=[product.pk])
    resp = client.post(url, {"photo": [png("a.png"), png("b.png", "blue")]}, format="multipart")
    assert resp.status_code == 201
    data = resp.json()
    assert data["photo"] and len(data["photos"]) == 1
    gallery_id = data["photos"][0]["id"]
    main_before = data["photo"]

    swap = client.post(reverse("products:manage-product-photo-op", args=[product.pk, gallery_id, "main"])).json()
    assert swap["photo"] != main_before and swap["photos"][0]["url"] == main_before

    gone = client.post(reverse("products:manage-product-photo-op", args=[product.pk, "main", "delete"])).json()
    assert gone["photo"] == main_before and gone["photos"] == []  # главным стало фото из галереи

    bad = client.post(url, {"photo": SimpleUploadedFile("x.png", b"not an image")}, format="multipart")
    assert bad.status_code == 400


def test_bulk_and_delete(client, seller):
    p1 = ProductVariantFactory(product__seller=seller, available=False).product
    p2 = ProductVariantFactory(product__seller=seller, available=False).product
    alien = ProductVariantFactory(product__seller=SellerFactory(), available=False).product
    category = CategoryFactory()
    bulk = reverse("products:manage-product-bulk")
    assert client.post(bulk, {"ids": [p1.pk, p2.pk, alien.pk], "action": "show"}, format="json").json() == {
        "changed": 2
    }
    assert not ProductVariant.objects.get(product=alien).available
    client.post(bulk, {"ids": [p1.pk], "action": "category", "category": category.pk}, format="json")
    p1.refresh_from_db()
    assert p1.category == category

    # с движением по складу удалить нельзя — только скрыть
    wh = WarehouseFactory(seller=seller)
    stock.receive(p1.variants.first(), wh, 1, supplier=SupplierFactory())
    resp = client.delete(detail(p1.pk))
    assert resp.status_code == 400 and Product.objects.filter(pk=p1.pk).exists()
    assert client.delete(detail(p2.pk)).status_code == 204

    only = reverse("products:manage-variant-detail", args=[p1.variants.first().pk])
    assert client.delete(only).status_code == 400  # единственный вариант
