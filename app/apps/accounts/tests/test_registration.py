import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.models import User

pytestmark = pytest.mark.django_db


def test_register_success(client: APIClient):
    url = reverse("dj-rest-auth:rest_register")
    data = {
        "email": "newuser@gmail.com",
        "username": "testuser",
        "password1": "Qwerty123!",
        "password2": "Qwerty123!",
    }
    response = client.post(url, data, format="json")
    assert response.status_code == 201
    assert User.objects.filter(email="newuser@gmail.com").exists()


def test_register_invalid_domain(client: APIClient):
    url = reverse("dj-rest-auth:rest_register")
    data = {
        "email": "hacker@unknown-domain.com",
        "username": "hacker",
        "password1": "Qwerty123!",
        "password2": "Qwerty123!",
    }
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "Регистрация доступна только" in str(response.data["email"][0])


def test_register_forbidden_word_in_password(client: APIClient):
    url = reverse("dj-rest-auth:rest_register")
    data = {
        "email": "newuser@gmail.com",
        "password1": "mypassword123",
        "password2": "mypassword123",
    }
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "password" in str(response.data["password1"][0])


def test_password_is_never_stored_in_plaintext(client):
    from django.db import connection

    from app.apps.accounts.models import Profile, User

    resp = client.post(
        reverse("dj-rest-auth:rest_register"),
        {"email": "secure@ukr.net", "password1": "Sup3r-Secret!9", "password2": "Sup3r-Secret!9"},
        format="json",
    )
    assert resp.status_code == 201, resp.json()
    user = User.objects.get(email="secure@ukr.net")
    assert user.password.startswith(("pbkdf2_", "md5$", "argon2", "bcrypt"))  # только хэш
    profile_columns = {
        c.name for c in connection.introspection.get_table_description(connection.cursor(), Profile._meta.db_table)
    }
    assert "password" not in profile_columns
