import pytest
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.sellers.models import Seller

pytestmark = pytest.mark.django_db
URL = "/api/sellers/sellers/"


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


def test_seller_registration_requires_approval_and_ignores_commission():
    user = UserFactory()
    resp = _client(user).post(URL, {"shop_name": "Сантех+", "commission_percent": "0"}, format="json")
    assert resp.status_code == 201, resp.json()
    seller = Seller.objects.get(user=user)
    assert seller.is_approved is False
    assert seller.commission_percent == 15  # значение по умолчанию, не из запроса
    assert _client(user).post(URL, {"shop_name": "Второй"}, format="json").status_code == 400


def test_seller_cannot_change_commission_or_delete_self():
    user = UserFactory()
    seller = Seller.objects.create(user=user, shop_name="Магазин", is_approved=True)
    c = _client(user)
    c.patch(f"{URL}{seller.pk}/", {"commission_percent": "1"}, format="json")
    seller.refresh_from_db()
    assert seller.commission_percent == 15
    assert c.delete(f"{URL}{seller.pk}/").status_code == 405
