import pytest
from django.urls import reverse
from rest_framework.test import APIClient
from app.apps.accounts.tests.factories import UserFactory
from app.apps.accounts.models import User, Profile

pytestmark = pytest.mark.django_db

def test_profile_retrieve():
    user = UserFactory(password="Qwerty123!")
    client = APIClient()
    client.force_authenticate(user=user)
    url = reverse("dj-rest-auth:profile")
    response = client.get(url)
    assert response.status_code == 200
    assert response.data["email"] == user.email

def test_profile_update():
    user = UserFactory(password="Qwerty123!")
    client = APIClient()
    client.force_authenticate(user=user)
    url = reverse("dj-rest-auth:profile")
    response = client.patch(url, {"first_name": "Ivan"}, format="json")
    assert response.status_code == 200
    user.refresh_from_db()
    assert user.first_name == "Ivan"



@pytest.mark.django_db
def test_profile_created_after_user():
    user = User.objects.create_user(email="test@example.com", password="Qwerty123!")
    profile = Profile.objects.get(user=user)
    assert profile.email == user.email