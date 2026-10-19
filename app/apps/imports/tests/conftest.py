import pytest
from rest_framework.test import APIClient

from app.apps.warehouse.tests.factories import SellerFactory, WarehouseFactory


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def wh(seller):
    return WarehouseFactory(seller=seller, is_default=True)


@pytest.fixture
def client(seller):
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


@pytest.fixture(autouse=True)
def photo_requests(monkeypatch):
    """Фото в тестах не скачиваются из интернета: запросы записываются, ответ — ошибка сети."""
    from app.apps.imports import photos

    calls = []

    def offline(url, **kwargs):
        calls.append(url)
        raise photos.FetchError("offline")

    monkeypatch.setattr(photos, "fetch", offline)
    return calls
