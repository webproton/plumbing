"""Письма покупателю: язык заказа, каждое событие один раз, ТТН, отделение, оплата, отмена, повтор."""

from decimal import Decimal

import pytest
from django.core import mail
from django.core.mail import EmailMultiAlternatives
from django.urls import reverse
from django.utils import translation
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.callback.models import SiteSettings
from app.apps.delivery import novaposhta as np
from app.apps.delivery import services as delivery
from app.apps.orders import services
from app.apps.orders.models import Order
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, stock_up
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db
TTN = "20450000000000"


@pytest.fixture
def run(django_capture_on_commit_callbacks):
    """Выполнить код и отложенные on_commit-задачи (письма уходят после коммита)."""

    def _run(fn, *args, **kwargs):
        with django_capture_on_commit_callbacks(execute=True):
            return fn(*args, **kwargs)

    return _run


@pytest.fixture
def admin():
    client = APIClient()
    client.force_authenticate(UserFactory(is_superuser=True))
    return client


def _order(run, lang="uk", email="client@test.com", user=None):
    variant = ProductVariantFactory(product=ProductFactory(), price=Decimal("1250.50"))
    stock_up(variant, 20)
    cart = CartFactory()
    CartItemsFactory(cart=cart, product=variant.product, variant=variant, quantity=10, stocked=0)
    fields = {"customer_name": "Олена Коваль", "phone_number": "+380501234567", "address": "Київ, Відділення №12"}
    with translation.override(lang):
        return run(services.create_order_from_cart, cart, user=user, email=email, **fields)


def test_created_email_in_order_language(run):
    order = _order(run, user=UserFactory())
    assert order.language == "uk"
    msg = mail.outbox[-1]
    assert msg.subject == f"Замовлення №{order.pk} прийнято"
    assert "Вітаємо, Олена Коваль!" in msg.body
    assert "10 × 1 250,50 ₴ = 12 505,00 ₴" in msg.body and "Разом: 12 505,00 ₴" in msg.body
    assert f"/account/orders/{order.pk}" in msg.body and "/ru/" not in msg.body
    html, mimetype = msg.alternatives[0]
    assert mimetype == "text/html" and "Олена Коваль" in html
    assert order.notifications.get().status == "sent"

    ru = _order(run, lang="ru")
    assert ru.language == "ru"
    assert mail.outbox[-1].subject == f"Заказ №{ru.pk} принят" and "Итого: 12 505,00 ₴" in mail.outbox[-1].body


def test_shipped_with_ttn_is_sent_once_new_number_gets_own_email(run):
    order = _order(run)
    mail.outbox.clear()
    run(delivery.set_ttn, order, "2045 0000 0000 00")
    assert [m.subject for m in mail.outbox] == [f"Замовлення №{order.pk} відправлено"]
    assert TTN in mail.outbox[0].body and f"cargo_number={TTN}" in mail.outbox[0].body

    run(delivery.set_ttn, order, TTN)  # тот же номер ещё раз — письма нет
    assert len(mail.outbox) == 1

    run(delivery.set_ttn, order, "20450000000001")
    assert mail.outbox[-1].subject == f"ТТН для замовлення №{order.pk}"
    assert "20450000000001" in mail.outbox[-1].body
    assert [n.key for n in order.notifications.all()] == ["created", "shipped", "ttn:20450000000001"]


def test_shipped_without_ttn_then_ttn_email(run):
    order = _order(run)
    mail.outbox.clear()
    run(services.change_status, order, Order.STATUS.delivering)
    assert "окремим листом" in mail.outbox[-1].body
    run(delivery.set_ttn, order, TTN)
    assert mail.outbox[-1].subject == f"ТТН для замовлення №{order.pk}" and TTN in mail.outbox[-1].body


def test_arrived_at_branch_once(run, monkeypatch):
    order = _order(run)
    run(delivery.set_ttn, order, TTN)
    mail.outbox.clear()
    monkeypatch.setattr(np, "track", lambda docs: [{"number": TTN, "status": "Прибув у відділення", "code": "7"}])
    run(delivery.refresh_statuses, [Order.objects.get(pk=order.pk)])
    run(delivery.refresh_statuses, [Order.objects.get(pk=order.pk)])  # опрос через 2 часа — повтора нет
    assert [m.subject for m in mail.outbox] == [f"Замовлення №{order.pk} чекає на вас у відділенні"]
    assert "Київ, Відділення №12" in mail.outbox[0].body


def test_paid_once_and_canceled_from_cabinet(run, admin):
    order = _order(run)
    mail.outbox.clear()
    url = reverse("orders:manage-order-payment", args=[order.pk])
    run(admin.post, url, {"payment_status": "paid_for"}, format="json")
    run(admin.post, url, {"payment_status": "paid_for"}, format="json")
    assert [m.subject for m in mail.outbox] == [f"Оплату за замовлення №{order.pk} отримано"]

    status_url = reverse("orders:manage-order-status", args=[order.pk])
    card = run(admin.post, status_url, {"status": "canceled"}, format="json").json()
    assert mail.outbox[-1].subject == f"Замовлення №{order.pk} скасовано"
    card = admin.get(reverse("orders:manage-order-detail", args=[order.pk])).json()
    assert [(n["event"], n["status"]) for n in card["notifications"]] == [
        ("created", "sent"),
        ("paid", "sent"),
        ("canceled", "sent"),
    ]
    assert card["notify_customers"] is True


def test_nothing_when_disabled_or_no_email(run):
    SiteSettings.objects.create(phone="1", notify_customers=False)
    order = _order(run)
    assert mail.outbox == [] and not order.notifications.exists()

    SiteSettings.objects.update(notify_customers=True)
    _order(run, email="")
    assert mail.outbox == []


def test_failed_email_is_logged_and_can_be_resent(run, admin, monkeypatch):
    def smtp_down(self, *args, **kwargs):
        raise ConnectionRefusedError("smtp down")

    monkeypatch.setattr(EmailMultiAlternatives, "send", smtp_down)
    order = _order(run)  # заказ оформлен, несмотря на сбой почты
    note = order.notifications.get()
    assert note.status == "failed" and "smtp down" in note.error
    monkeypatch.undo()

    url = reverse("orders:manage-order-notification-resend", kwargs={"pk": order.pk, "note_id": note.pk})
    card = admin.post(url).json()
    assert card["notifications"][0]["status"] == "sent" and card["notifications"][0]["error"] == ""
    assert len(mail.outbox) == 1
