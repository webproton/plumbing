"""
Контракт авторизации — ровно те адреса и форматы, которыми пользуется витрина (frontend/web).
Должен проходить без изменений при обновлении Django / allauth / dj-rest-auth.
"""

import re

import pytest
from django.conf import settings
from django.core import mail
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db
A = "/api/dj-rest-auth"
EMAIL, PASSWORD = "olena.koval@gmail.com", "Kran-Kulovyi-2026"


def _tokens(data):
    return data.get("access") or data.get("access_token"), data.get("refresh") or data.get("refresh_token")


def _register_and_confirm(c):
    resp = c.post(f"{A}/registration/", {"email": EMAIL, "password1": PASSWORD, "password2": PASSWORD}, format="json")
    assert resp.status_code == 201, resp.content
    assert len(mail.outbox) == 1
    link = re.search(rf"{re.escape(settings.FRONTEND_URL)}/confirm-email/([^/\s]+)/", mail.outbox[0].body)
    assert link, mail.outbox[0].body
    return link.group(1)


def test_register_confirm_login_refresh_logout():
    c = APIClient()
    key = _register_and_confirm(c)
    assert (
        c.post(f"{A}/login/", {"email": EMAIL, "password": PASSWORD}, format="json").status_code == 400
    )  # не подтверждён

    assert c.post(f"{A}/registration/verify-email/", {"key": key}, format="json").status_code == 200
    resp = c.post(f"{A}/login/", {"email": EMAIL, "password": PASSWORD}, format="json")
    assert resp.status_code == 200, resp.content
    access, refresh = _tokens(resp.json())
    assert access and refresh

    auth = APIClient()
    auth.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
    assert auth.get(f"{A}/profile/").json()["email"] == EMAIL
    assert auth.patch(f"{A}/profile/", {"first_name": "Олена"}, format="json").json()["first_name"] == "Олена"
    assert auth.get("/api/warehouse/me/").json()["is_staff_user"] is False

    resp = c.post(f"{A}/token/refresh/", {"refresh": refresh}, format="json")
    assert resp.status_code == 200 and resp.json()["access"]
    new_refresh = resp.json().get("refresh", refresh)
    assert c.post(f"{A}/token/refresh/", {"refresh": refresh}, format="json").status_code == 401  # ротация

    assert auth.post(f"{A}/logout/", {"refresh": new_refresh}, format="json").status_code == 200
    assert c.post(f"{A}/token/refresh/", {"refresh": new_refresh}, format="json").status_code == 401  # в чёрном списке


def test_password_reset_flow():
    c = APIClient()
    key = _register_and_confirm(c)
    c.post(f"{A}/registration/verify-email/", {"key": key}, format="json")
    mail.outbox.clear()

    assert c.post(f"{A}/password/reset/", {"email": "nobody@gmail.com"}, format="json").status_code == 200
    assert mail.outbox == []  # не раскрываем, есть ли такой адрес
    assert c.post(f"{A}/password/reset/", {"email": EMAIL}, format="json").status_code == 200
    link = re.search(
        rf"{re.escape(settings.FRONTEND_URL)}/reset-password/confirm\?uid=([^&\s]+)&token=([^\s]+)", mail.outbox[0].body
    )
    assert link, mail.outbox[0].body
    uid, token = link.groups()
    new = "Zmishuvach-Novyi-77"
    data = {"uid": uid, "token": token, "new_password1": new, "new_password2": new}
    assert c.post(f"{A}/password/reset/confirm/", data, format="json").status_code == 200
    assert c.post(f"{A}/login/", {"email": EMAIL, "password": PASSWORD}, format="json").status_code == 400
    assert c.post(f"{A}/login/", {"email": EMAIL, "password": new}, format="json").status_code == 200


def test_bruteforce_lockout(settings):
    settings.AXES_FAILURE_LIMIT = 3
    c = APIClient()
    key = _register_and_confirm(c)
    c.post(f"{A}/registration/verify-email/", {"key": key}, format="json")
    for _ in range(3):
        c.post(f"{A}/login/", {"email": EMAIL, "password": "wrong-password"}, format="json")
    resp = c.post(f"{A}/login/", {"email": EMAIL, "password": PASSWORD}, format="json")
    # даже верный пароль не пускает после блокировки (django-axes)
    assert resp.status_code in (400, 403, 429) and not any(_tokens(resp.json())), resp.content
