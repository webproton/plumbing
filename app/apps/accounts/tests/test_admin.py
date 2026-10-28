import pytest
from allauth.account.models import EmailAddress
from django.test import Client
from django.urls import reverse

from app.apps.accounts.models import User

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin_client() -> Client:
    client = Client()
    client.force_login(User.objects.create_superuser("boss@example.com", "Str0ngPass!"))
    return client


def test_admin_creates_user_with_hashed_password_and_verified_email(admin_client):
    response = admin_client.post(
        reverse("admin:accounts_user_add"),
        {"email": "seller@example.com", "password1": "Sup3r-secret-1", "password2": "Sup3r-secret-1"},
    )
    assert response.status_code == 302
    user = User.objects.get(email="seller@example.com")
    assert user.password != "Sup3r-secret-1"  # не текстом
    assert user.check_password("Sup3r-secret-1")
    assert EmailAddress.objects.filter(user=user, email="seller@example.com", verified=True, primary=True).exists()


def test_admin_user_pages_open(admin_client):
    user = User.objects.create_user("buyer@example.com", "Sup3r-secret-1")
    assert admin_client.get(reverse("admin:accounts_user_changelist")).status_code == 200
    assert admin_client.get(reverse("admin:accounts_user_change", args=[user.pk])).status_code == 200
    assert admin_client.get(reverse("admin:accounts_user_add")).status_code == 200
