import pytest
from allauth.account.models import EmailAddress
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db


def test_login_success(client: APIClient):
    user = UserFactory(password="Qwerty123!")
    EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
    url = reverse("dj-rest-auth:rest_login")
    data = {"email": user.email, "password": "Qwerty123!"}
    response = client.post(url, data, format="json")
    assert response.status_code == 200
    # dj-rest-auth ≥ 4 отдаёт access/refresh (раньше access_token/refresh_token) — витрина понимает оба
    assert response.data.get("access") and response.data.get("refresh")


def test_login_bad_password(client: APIClient):
    user = UserFactory(password="Qwerty123!")
    url = reverse("dj-rest-auth:rest_login")
    data = {"email": user.email, "password": "badpassword"}
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "non_field_errors" in response.data


@pytest.mark.django_db
def test_create_superuser_sets_admin_and_superuser_flags():
    from app.apps.accounts.models import User

    admin = User.objects.create_superuser("boss@example.com", "Str0ngPass!")
    assert admin.is_superuser and admin.is_admin and admin.is_staff and admin.is_active
    user = User.objects.create_user("u@example.com", "Str0ngPass!", first_name="Олена", last_name="Коваль")
    assert (user.first_name, user.last_name, user.is_superuser) == ("Олена", "Коваль", False)


@pytest.mark.django_db
def test_create_managers_uses_random_passwords(monkeypatch):
    import io

    from django.core.management import call_command

    from app.apps.accounts.models import User

    monkeypatch.setenv("MANAGERS", "")
    out = io.StringIO()
    call_command("create_managers", stdout=out)
    users = User.objects.filter(email__startswith="im_manager_")
    assert users.count() == 5 and not any(u.check_password("manager123") for u in users)
    assert "пароль:" in out.getvalue()
