from decimal import Decimal
from io import BytesIO

import pdfplumber
import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse.labels import generate_labels, is_ean13
from app.apps.warehouse.tests.factories import SellerFactory

pytestmark = pytest.mark.django_db


def test_ean13_check_digit():
    assert is_ean13("4820000000017") and is_ean13("4006381333931")
    assert not is_ean13("4820000000018") and not is_ean13("2123") and not is_ean13("ABC")


def test_generate_both_sizes():
    v1 = ProductVariantFactory(
        variant_name="Змішувач для кухні з дуже довгою назвою, яка не влазить у два рядки",
        price=Decimal("1250.50"),
        barcode="4006381333931",
        code="GR-1",
    )
    v2 = ProductVariantFactory(price=Decimal("99"), barcode="2123456789012", code="X-2")  # не EAN → Code128
    thermal = generate_labels([v1, v2], size="thermal", copies=2, shop="Магазин")
    with pdfplumber.open(BytesIO(thermal)) as pdf:
        assert len(pdf.pages) == 4  # 2 товара × 2 копии, по этикетке на странице
        text = pdf.pages[0].extract_text()
        assert "Магазин" in text and "1250,50" in text and "GR-1" in text and "…" in text
    with pdfplumber.open(BytesIO(generate_labels([v1] * 30, size="a4"))) as pdf:
        assert len(pdf.pages) == 2  # 24 на листе


def test_labels_api_scope():
    seller = SellerFactory()
    mine = ProductVariantFactory(product__seller=seller)
    alien = ProductVariantFactory(product__seller=SellerFactory())
    c = APIClient()
    c.force_authenticate(seller.user)
    url = reverse("warehouse:labels")
    resp = c.get(url, {"variants": f"{mine.pk},{alien.pk}", "size": "a4"})
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
    assert c.get(url, {"variants": str(alien.pk)}).status_code == 404  # чужие не печатаются
    assert c.get(url, {"products": str(mine.product_id), "copies": "3"}).status_code == 200
    assert c.get(url).status_code == 400
    buyer = APIClient()
    buyer.force_authenticate(UserFactory())
    assert buyer.get(url, {"variants": str(mine.pk)}).status_code == 403
