import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from app.apps.accounts.tests.factories import UserFactory

pytestmark = pytest.mark.django_db

def test_login_success(client: APIClient):
    user = UserFactory(password="Qwerty123!")
    url = reverse("dj-rest-auth:rest_login")
    data = {"email": user.email, "password": "Qwerty123!"}
    response = client.post(url, data, format="json")
    assert response.status_code == 200
    assert "access_token" in response.data  # JWT токен

def test_login_bad_password(client: APIClient):
    user = UserFactory(password="Qwerty123!")
    url = reverse("dj-rest-auth:rest_login")
    data = {"email": user.email, "password": "badpassword"}
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "non_field_errors" in response.data

def test_login_with_forbidden_word_in_password(client: APIClient):
    user = UserFactory(password="mypassword123")
    url = reverse("dj-rest-auth:rest_login")
    data = {"email": user.email, "password": "mypassword123"}
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "Нельзя использовать 'password'" in str(response.data["non_field_errors"][0])


def test_login_forbidden_word_in_password(client: APIClient):
    # Создаём пользователя с любым паролем (важно, что он не проверяется при логине)
    user = UserFactory(password="Qwerty123!")
    url = reverse("dj-rest-auth:rest_login")
    data = {
        "email": user.email,
        "password": "mypassword123",  # содержит запрещённое слово
    }
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "Нельзя использовать 'password'" in str(response.data["non_field_errors"][0])