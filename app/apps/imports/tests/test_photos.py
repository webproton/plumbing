"""Фото поставщиков: уменьшаем перед сохранением и бережём диск сервера."""

from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from app.apps.imports import photos
from app.apps.products.tests.factories import ProductVariantFactory

pytestmark = pytest.mark.django_db


def _png(width, height) -> bytes:
    out = BytesIO()
    Image.new("RGBA", (width, height), (200, 30, 30, 128)).save(out, "PNG")
    return out.getvalue()


def test_photos_are_shrunk_to_jpeg_and_capped(monkeypatch):
    big = _png(3200, 2000)
    monkeypatch.setattr(photos, "fetch", lambda url, **kw: SimpleNamespace(content=big))
    variant = ProductVariantFactory()
    saved = photos.download_product_photos(variant.pk, [f"https://cdn.example.com/{i}.png" for i in range(10)])
    assert saved == photos.MAX_PHOTOS == 6
    product = variant.product
    product.refresh_from_db()
    with Image.open(product.photo.path) as img:
        assert img.format == "JPEG" and max(img.size) == 1600
    assert product.photo.size < len(big)


def test_no_download_when_disk_is_almost_full(monkeypatch):
    monkeypatch.setattr(photos, "fetch", lambda url, **kw: SimpleNamespace(content=_png(100, 100)))
    monkeypatch.setattr(photos, "disk_full", lambda: True)
    variant = ProductVariantFactory()
    assert photos.download_product_photos(variant.pk, ["https://cdn.example.com/1.png"]) == 0
    variant.product.refresh_from_db()
    assert not variant.product.photo
