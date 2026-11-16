"""Список закупки: пишут как удобно — строки становятся заказом у поставщиков."""

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.imports import services as imports
from app.apps.imports.models import ImportSource, SupplierItem
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.models import PurchaseLine, PurchaseList
from app.apps.warehouse.purchase import parse_line
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def client(seller):
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


def test_parse_line_keeps_sizes_and_finds_quantity():
    assert parse_line("футорки 20 1/2 в") == ("футорки 20 1/2 в", Decimal(1), "")
    assert parse_line("фитинги 16") == ("фитинги 16", Decimal(1), "")  # 16 — размер, не количество
    assert parse_line("футорки 20 1/2 в — 10 шт") == ("футорки 20 1/2 в", Decimal(10), "шт")
    assert parse_line("труба ppr 20 50м") == ("труба ppr 20", Decimal(50), "м")
    assert parse_line("шланг 1 м — 5 шт") == ("шланг 1 м", Decimal(5), "шт")
    assert parse_line("кран 1/2 x4") == ("кран 1/2", Decimal(4), "")
    assert parse_line("бойлер 80 л") == ("бойлер 80 л", Decimal(1), "")  # литры — объём, не количество


def _offer_from_invoice(seller, variant, supplier, price):
    wh = WarehouseFactory(seller=seller)
    stock.receive(variant, wh, 5, supplier=supplier, price_per_unit=Decimal(price))


def test_lines_become_order_objects_and_assemble_by_supplier(client, seller):
    secvoia, other = SupplierFactory(name="Секвоя", phone="+380671112233"), SupplierFactory(name="Аквадом")
    futorka = ProductVariantFactory(product__seller=seller, product__name="Футорка PPR 20х1/2 ВР", code="FT-20")
    _offer_from_invoice(seller, futorka, secvoia, "12.40")
    _offer_from_invoice(seller, futorka, other, "13.90")

    resp = client.post(reverse("warehouse:purchase_lines"), {"texts": ["футорки 20 1/2 в — 10 шт", "фитинги 16"]}, format="json")
    assert resp.status_code == 201, resp.content
    first, second = resp.json()["lines"]
    # один свой товар нашёлся — выбран сам, у самого дешёвого поставщика
    assert first["choice"]["variant"] == futorka.pk and first["auto"] is True
    assert first["supplier_name"] == "Секвоя" and first["price"] == "12.40" and first["quantity"] == "10"
    assert second["choice"] is None  # «фитинги 16» — не нашлось, остаётся записью

    options = client.get(reverse("warehouse:purchase_line_options", args=[first["id"]])).json()
    offers = options["products"][0]["offers"]
    assert [o["supplier_name"] for o in offers] == ["Секвоя", "Аквадом"] and offers[0]["best"] is True

    # человек выбрал другого поставщика
    client.patch(reverse("warehouse:purchase_line", args=[first["id"]]),
                 {"variant": futorka.pk, "supplier": other.pk, "price": "13.90"}, format="json")
    order = client.get(reverse("warehouse:purchase_assemble")).json()
    groups = {g["supplier"]: g for g in order["groups"]}
    assert groups["Аквадом"]["total"] == "139.00"
    assert "Футорка PPR 20х1/2 ВР (FT-20) — 10 шт" in groups["Аквадом"]["message"]
    assert groups[""]["lines"][0]["text"] == "фитинги 16"  # без поставщика — отдельной группой, в конце
    assert order["groups"][-1]["key"] == "none"


def test_same_entry_next_time_takes_last_choice(client, seller):
    supplier = SupplierFactory(name="Секвоя")
    a = ProductVariantFactory(product__seller=seller, product__name="Футорка 20х1/2 ВР")
    ProductVariantFactory(product__seller=seller, product__name="Футорка 20х3/4 ВР")
    _offer_from_invoice(seller, a, supplier, "12.40")
    line = client.post(reverse("warehouse:purchase_lines"), {"texts": ["футорки 20"]}, format="json").json()["lines"][0]
    assert line["choice"] is None  # два похожих товара — сама не выбирает
    client.patch(reverse("warehouse:purchase_line", args=[line["id"]]), {"variant": a.pk}, format="json")
    assert client.post(reverse("warehouse:purchase_ordered")).json()["lines"] == []  # новый пустой список

    again = client.post(reverse("warehouse:purchase_lines"), {"texts": ["Футорки 20 — 6 шт"]}, format="json").json()["lines"][0]
    assert again["choice"]["variant"] == a.pk and again["supplier_name"] == "Секвоя" and again["auto"] is True
    assert again["quantity"] == "6"
    options = client.get(reverse("warehouse:purchase_line_options", args=[again["id"]])).json()
    assert options["last_time"]["variant"] == a.pk


def test_supplier_items_not_in_catalog_and_isolation(client, seller):
    source = ImportSource(seller=seller, name="sanwell", kind="feed")
    source.file.save(
        "feed.yml",
        SimpleUploadedFile(
            "feed.yml",
            """<yml_catalog><shop><currencies><currency id="EUR"/></currencies><categories><category id="1">Фітинги</category></categories>
            <offers><offer id="A" available="true"><name>GEBO ANB врізка в трубу DN100</name><price>66.42</price>
            <currencyId>EUR</currencyId><categoryId>1</categoryId><vendorCode>GB-100</vendorCode></offer></offers></shop></yml_catalog>""".encode(),
        ),
        save=False,
    )
    source.save()
    imports.sync_source(source)
    line = client.post(reverse("warehouse:purchase_lines"), {"texts": ["gebo dn100"]}, format="json").json()["lines"][0]
    options = client.get(reverse("warehouse:purchase_line_options", args=[line["id"]])).json()
    item = options["items"][0]
    assert item["name"].startswith("GEBO") and item["supplier_name"] == "sanwell" and item["price"] is None  # курса EUR нет
    chosen = client.patch(reverse("warehouse:purchase_line", args=[line["id"]]), {"item": item["item"]}, format="json").json()
    assert chosen["choice"]["item"] == SupplierItem.objects.get(external_id="A").pk and chosen["supplier_name"] == "sanwell"

    stranger = APIClient()
    stranger.force_authenticate(SellerFactory().user)
    assert stranger.get(reverse("warehouse:purchase_line_options", args=[line["id"]])).status_code == 404
    assert stranger.delete(reverse("warehouse:purchase_line", args=[line["id"]])).status_code == 404
    assert PurchaseLine.objects.count() == 1 and PurchaseList.objects.filter(seller=seller).count() == 1


def test_add_from_stock_page_and_quantity(client, seller):
    supplier = SupplierFactory(name="Секвоя")
    variant = ProductVariantFactory(product__seller=seller, product__name="Кран кульовий 1/2")
    _offer_from_invoice(seller, variant, supplier, "210")
    line = client.post(reverse("warehouse:purchase_lines"), {"variants": [variant.pk]}, format="json").json()["lines"][0]
    assert line["choice"]["variant"] == variant.pk and line["supplier_name"] == "Секвоя"
    resp = client.patch(reverse("warehouse:purchase_line", args=[line["id"]]), {"quantity": "3"}, format="json")
    assert resp.json()["quantity"] == "3"
    assert client.patch(reverse("warehouse:purchase_line", args=[line["id"]]), {"quantity": "0"}, format="json").status_code == 400
