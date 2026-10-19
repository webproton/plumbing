"""Нова Пошта: справочники, стоимость, ТТН (вручную и через API), отслеживание → «Доставлен»."""

from decimal import Decimal

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.callback.models import SiteSettings
from app.apps.delivery import novaposhta as np
from app.apps.delivery import tasks
from app.apps.orders import services
from app.apps.orders.tests.factories import CartFactory, CartItemsFactory, stock_up
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory

pytestmark = pytest.mark.django_db
CITY = "8d5a980d-391c-11dd-90d9-001a92567626"
WAREHOUSE = "731a002c-3ed2-11e6-a9f2-005056887b8d"


class FakeNP:
    """Подмена requests.post: ответы в формате API Новой Почты по calledMethod."""

    def __init__(self):
        self.calls, self.statuses = [], {}

    def __call__(self, url, json=None, timeout=None):
        self.calls.append(json)
        method = json["calledMethod"]
        data = {
            "searchSettlements": [
                {
                    "Addresses": [
                        {
                            "Present": "м. Київ, Київська обл.",
                            "MainDescription": "Київ",
                            "DeliveryCity": CITY,
                            "Warehouses": 12719,
                        },
                        {
                            "Present": "с. Київець",
                            "MainDescription": "Київець",
                            "DeliveryCity": "x" * 36,
                            "Warehouses": 0,
                        },
                    ]
                }
            ],
            "getWarehouses": [
                {
                    "Ref": WAREHOUSE,
                    "Number": "12",
                    "Description": "Відділення №12: вул. Бунге, 8",
                    "DescriptionRu": "Отделение №12",
                    "CategoryOfWarehouse": "Branch",
                    "TotalMaxWeightAllowed": "0",
                    "WarehouseStatus": "Working",
                },
                {
                    "Ref": "p" * 36,
                    "Number": "1001",
                    "Description": "Поштомат №1001",
                    "CategoryOfWarehouse": "Postomat",
                    "TotalMaxWeightAllowed": "20",
                    "WarehouseStatus": "Working",
                },
                {
                    "Ref": "c" * 36,
                    "Number": "7",
                    "Description": "Закрите",
                    "CategoryOfWarehouse": "Branch",
                    "WarehouseStatus": "NotWorking",
                },
            ],
            "getDocumentPrice": [{"Cost": 95, "AssessedCost": 1000}],
            "getDocumentDeliveryDate": [{"DeliveryDate": {"date": "2026-10-21 18:00:00.000000"}}],
            "getStatusDocuments": [
                {
                    "Number": d["DocumentNumber"],
                    "Status": self.statuses.get(d["DocumentNumber"], ("Прямує", "5"))[0],
                    "StatusCode": self.statuses.get(d["DocumentNumber"], ("", "5"))[1],
                }
                for d in json["methodProperties"].get("Documents", [])
            ],
            "getCounterparties": [{"Ref": "sender-ref"}],
            "getCounterpartyContactPersons": [{"Ref": "contact-ref"}],
            "save": (
                [
                    {
                        "Ref": "doc-ref",
                        "IntDocNumber": "20450000000001",
                        "CostOnSite": 95,
                        "EstimatedDeliveryDate": "21.10.2026",
                    }
                ]
                if json["modelName"] == "InternetDocument"
                else [{"Ref": "recipient-ref", "ContactPerson": {"data": [{"Ref": "rcontact-ref"}]}}]
            ),
        }.get(method)
        ok = data is not None
        return type(
            "R", (), {"json": lambda self: {"success": ok, "data": data or [], "errors": [] if ok else ["Bad"]}}
        )()


@pytest.fixture
def fake(monkeypatch):
    f = FakeNP()
    monkeypatch.setattr(np.requests, "post", f)
    return f


def _order(**fields):
    variant = ProductVariantFactory(product=ProductFactory(), price=Decimal("1250.50"))
    stock_up(variant, 5)
    variant = ProductVariant.objects.get(pk=variant.pk)
    cart = CartFactory()
    CartItemsFactory(cart=cart, product=variant.product, variant=variant, quantity=2, stocked=0)
    data = {"customer_name": "Олена Коваль", "phone_number": "+380501234567", "address": "НП Київ 12", **fields}
    return services.create_order_from_cart(cart, **data), variant


def test_public_lookup(fake):
    c = APIClient()
    cities = c.get(reverse("delivery:np-cities"), {"q": "київ"}).json()
    assert cities == [{"ref": CITY, "name": "Київ", "label": "м. Київ, Київська обл.", "warehouses": 12719}]
    c.get(reverse("delivery:np-cities"), {"q": "київ"})
    assert len(fake.calls) == 1  # из кэша
    assert c.get(reverse("delivery:np-cities"), {"q": "к"}).json() == []

    whs = c.get(reverse("delivery:np-warehouses"), {"city": CITY, "q": "12"}).json()
    assert [(w["number"], w["kind"], w["max_weight"]) for w in whs] == [
        ("12", "branch", None),
        ("1001", "postomat", 20),
    ]
    ru = c.get(reverse("delivery:np-warehouses"), {"city": CITY, "q": "12"}, HTTP_ACCEPT_LANGUAGE="ru").json()
    assert ru[0]["name"] == "Отделение №12"

    est = reverse("delivery:np-estimate")
    assert c.get(est, {"city": CITY, "cost": 1000}).json() == {}  # нет города отправителя
    SiteSettings.objects.create(phone="1", np_sender_city_ref="db5c88f0-391c-11dd-90d9-001a92567626")
    assert c.get(est, {"city": CITY, "cost": 1000}).json() == {"cost": 95, "date": "2026-10-21"}


def test_api_error_becomes_503(monkeypatch):
    def broken(*a, **kw):
        raise np.requests.ConnectionError("down")

    monkeypatch.setattr(np.requests, "post", broken)
    assert APIClient().get(reverse("delivery:np-cities"), {"q": "львів"}).status_code == 503


def test_order_keeps_np_refs():
    order, _v = _order(np_city_ref=CITY, np_warehouse_ref=WAREHOUSE)
    assert (order.np_city_ref, order.np_warehouse_ref) == (CITY, WAREHOUSE)


def test_manual_ttn_tracking_and_auto_delivered(fake):
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    order, variant = _order()
    url = reverse("orders:manage-order-ttn", args=[order.pk])
    assert admin.post(url, {"ttn": "123"}, format="json").status_code == 400
    card = admin.post(url, {"ttn": "2045 0000 0000 00"}, format="json").json()
    assert card["ttn"] == "20450000000000" and card["status_order"] == "delivering" and card["ttn_status"] == "Прямує"

    fake.statuses["20450000000000"] = ("Відправлення отримано", "9")
    assert tasks.refresh_ttn_statuses() == 1
    order.refresh_from_db()
    variant.refresh_from_db()
    assert order.status_order == "delivered" and order.ttn_status_code == "9"
    assert (variant.stock, variant.reserved) == (Decimal("3.000"), Decimal("0.000"))  # списано со склада
    assert tasks.refresh_ttn_statuses() == 0  # окончательный статус больше не опрашивается


def test_create_ttn_via_api(fake):
    admin = APIClient()
    admin.force_authenticate(UserFactory(is_superuser=True))
    order, _v = _order(np_city_ref=CITY, np_warehouse_ref=WAREHOUSE)
    url = reverse("orders:manage-order-ttn-create", args=[order.pk])
    assert admin.post(url, {"weight": 2}, format="json").status_code == 400  # нет ключа

    with override_settings(NOVA_POSHTA_API_KEY="key"):
        resp = admin.post(url, {"weight": 2}, format="json")
        assert resp.status_code == 400 and "отправителя" in str(resp.json())
        SiteSettings.objects.create(
            phone="1", np_sender_city_ref=CITY, np_sender_warehouse_ref=WAREHOUSE, np_sender_phone="+380671112233"
        )
        card = admin.post(
            url, {"weight": 2.5, "seats": 1, "description": "Змішувач", "cod": True}, format="json"
        ).json()
    assert card["ttn"] == "20450000000001" and card["status_order"] == "delivering"
    doc = next(c for c in fake.calls if c["modelName"] == "InternetDocument" and c["calledMethod"] == "save")
    props = doc["methodProperties"]
    assert (props["Sender"], props["ContactSender"], props["Recipient"], props["ContactRecipient"]) == (
        "sender-ref", "contact-ref", "recipient-ref", "rcontact-ref",
    )  # fmt: skip
    assert (props["RecipientAddress"], props["Weight"], props["RecipientsPhone"]) == (WAREHOUSE, "2.5", "380501234567")
    assert props["BackwardDeliveryData"][0]["RedeliveryString"] == "2501.0"
    person = next(c for c in fake.calls if c["modelName"] == "Counterparty" and c["calledMethod"] == "save")
    assert (person["methodProperties"]["FirstName"], person["methodProperties"]["LastName"]) == ("Олена", "Коваль")
