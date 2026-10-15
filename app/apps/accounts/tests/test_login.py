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
    assert "access_token" in response.data  # JWT токен


def test_login_bad_password(client: APIClient):
    user = UserFactory(password="Qwerty123!")
    url = reverse("dj-rest-auth:rest_login")
    data = {"email": user.email, "password": "badpassword"}
    response = client.post(url, data, format="json")
    assert response.status_code == 400
    assert "non_field_errors" in response.data
