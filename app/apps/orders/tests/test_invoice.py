from decimal import Decimal
from io import BytesIO

import pdfplumber
import pytest
from django.core import mail
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.callback.models import SiteSettings
from app.apps.orders import services
from app.apps.orders.invoice import amount_in_words
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, stock_up
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "amount, words",
    [
        ("1143.00", "Одна тисяча сто сорок три гривні 00 копійок"),
        ("21.01", "Двадцять одна гривня 01 копійка"),
        ("2001.55", "Дві тисячі одна гривня 55 копійок"),
        ("11000", "Одинадцять тисяч гривень 00 копійок"),
        ("0.5", "Нуль гривень 50 копійок"),
    ],
)
def test_amount_in_words(amount, words):
    assert amount_in_words(Decimal(amount)) == words


def _order(user=None, email="client@test.com"):
    variant = ProductVariantFactory(product=ProductFactory(name="Змішувач"), price=Decimal("571.50"))
    stock_up(variant, 5)
    variant = ProductVariant.objects.get(pk=variant.pk)
    cart = CartFactory(customer=user)
    CartItemsFactory(cart=cart, product=variant.product, variant=variant, quantity=2, stocked=0)
    return services.create_order_from_cart(
        cart, user=user, customer_name="Олена Коваль", phone_number="+380501234567", address="НП", email=email
    )


def _requisites():
    return SiteSettings.objects.create(
        phone="+380671112233",
        legal_name="ФОП Тестовий Т.Т.",
        tax_id="1234567890",
        iban="UA" + "1" * 27,
        bank_name="АТ Банк",
    )


def test_manager_invoice_and_email():
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    order = _order()
    url = reverse("orders:manage-order-invoice", args=[order.pk])
    assert admin.get(url).status_code == 400  # нет реквизитов
    _requisites()
    resp = admin.get(url)
    assert resp.status_code == 200 and resp["Content-Type"] == "application/pdf"
    with pdfplumber.open(BytesIO(resp.content)) as pdf:
        text = pdf.pages[0].extract_text()
    assert f"Рахунок на оплату № {order.pk}" in text and "ФОП Тестовий" in text and "1 143,00" in text
    assert "Одна тисяча сто сорок три гривні 00 копійок" in text

    sent = admin.post(reverse("orders:manage-order-invoice-send", args=[order.pk])).json()
    assert sent == {"sent_to": "client@test.com"}
    assert mail.outbox[-1].attachments[0][0] == f"invoice-{order.pk}.pdf"


def test_buyer_invoice_access():
    _requisites()
    buyer = UserFactory()
    order = _order(user=buyer)
    c = APIClient()
    c.force_authenticate(buyer)
    detail = c.get(reverse("orders:user-orders-detail", args=[order.pk])).json()
    assert detail["can_download_invoice"] is True and detail["payment_status_display"]
    assert c.get(reverse("orders:user-orders-invoice", args=[order.pk])).status_code == 200
    other = APIClient()
    other.force_authenticate(UserFactory())
    assert other.get(reverse("orders:user-orders-invoice", args=[order.pk])).status_code == 404
    order.payment_status = "paid_for"
    order.save(update_fields=["payment_status"])
    assert c.get(reverse("orders:user-orders-invoice", args=[order.pk])).status_code == 400


def test_shop_settings_admin_only():
    url = reverse("callback:shop-settings")
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    assert admin.get(url).json()["np_key_configured"] is False
    assert admin.patch(url, {"iban": "UA123"}, format="json").status_code == 400
    data = admin.patch(
        url, {"iban": "ua" + "2" * 27, "legal_name": "ФОП Тест", "tax_id": "12345678"}, format="json"
    ).json()
    assert data["iban"] == "UA" + "2" * 27 and SiteSettings.current().has_requisites
    seller = APIClient()
    seller.force_authenticate(UserFactory())
    assert seller.get(url).status_code == 403
