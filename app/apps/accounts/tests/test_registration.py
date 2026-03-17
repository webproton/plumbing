import pytest
from rest_framework.test import APIClient
from django.urls import reverse
from app.apps.accounts.models import User
from app.apps.accounts.tests.factories import UserFactory


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
    assert "Нельзя использовать 'password'" in str(response.data["password1"][0])
