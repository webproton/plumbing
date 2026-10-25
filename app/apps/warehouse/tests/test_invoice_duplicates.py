"""Та же поставка не приходуется дважды: дубли накладных, приёмка сканером, отмена проведения (сторно)."""

import threading

import pytest
from django.db import connection
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.duplicates import number_key
from app.apps.warehouse.models import InventoryDocument, StockMovement
from app.apps.warehouse.services import DuplicateDocumentError, process_inventory_document
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory
from app.apps.warehouse.tests.test_api import _invoice_file

pytestmark = pytest.mark.django_db

HEADER = ["№", "Артикул", "Товар", "Кількість", "Ціна", "Сума"]
GOODS = [
    [1, "MIX-1", "Змішувач для кухні", 2, 1500, 3000],
    [2, "PPR-20", "Труба PPR 20мм", 10, 45, 450],
    [3, "KR-12", "Кран кульовий 1/2", 4, 210, 840],
    [4, "SF-1", "Сифон для мийки", 1, 300, 300],
    [5, "GS-1", "Гнучкий шланг 40 см", 5, 95, 475],
]


def rows(title="Видаткова накладна № 0077 від 01.10.2026", goods=GOODS):
    return [[title], HEADER, *goods]


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def wh(seller):
    return WarehouseFactory(seller=seller, is_default=True)


@pytest.fixture
def client(seller):
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


@pytest.fixture
def supplier():
    return SupplierFactory()


def upload(client, table=None, name="a.xlsx", **extra):
    resp = client.post(
        reverse("warehouse:inventorydocument-list"),
        {"document_type": "incoming", "file": _invoice_file(table or rows(), name), **extra},
        format="multipart",
    )
    assert resp.status_code == 201, resp.json()
    return resp.json()


def process(client, doc_id, **data):
    return client.post(reverse("warehouse:inventorydocument-process", args=[doc_id]), data, format="json")


def stock_of(code):
    return ProductVariant.objects.get(code=code).stock


def test_number_key_ignores_formatting():
    assert number_key("№ 00123") == number_key("123") == number_key(" 123 ") == "123"
    assert number_key("ВН-0045") == number_key("BH 45")  # кириллица/латиница, разделители, нули
    assert number_key("No 7") == number_key("N7") == "7"
    assert number_key(None) == number_key("") == ""


def test_same_invoice_with_number_written_differently_needs_confirmation(client, wh, supplier):
    first = upload(client, supplier=supplier.pk)
    assert process(client, first["id"]).status_code == 200

    copy = upload(client, rows("Видаткова накладна № 77 від 01.10.2026"), "copy.xlsx")  # поставщик не выбран
    assert [(d["id"], d["processed"], d["reasons"]) for d in copy["duplicates"]] == [
        (first["id"], True, ["content", "number"])
    ]
    blocked = process(client, copy["id"])
    assert blocked.status_code == 400 and blocked.json()["code"] == "duplicate_document"
    assert stock_of("MIX-1") == 2  # второй раз не оприходовано

    detail = reverse("warehouse:inventorydocument-detail", args=[copy["id"]])
    client.patch(detail, {"supplier": supplier.pk}, format="json")  # без поставщика приход не проводится
    confirmed = process(client, copy["id"], allow_duplicate=True)
    assert confirmed.status_code == 200, confirmed.json()
    assert confirmed.json()["duplicate_confirmed"]["documents"] == [first["id"]]


def test_copy_without_number_is_found_by_lines(client, wh, supplier):
    first = upload(client, supplier=supplier.pk)
    process(client, first["id"])
    copy = upload(client, rows("Видаткова накладна"), "photo-copy.xlsx", supplier=SupplierFactory().pk)
    assert [(d["id"], d["reasons"]) for d in copy["duplicates"]] == [(first["id"], ["content"])]
    assert process(client, copy["id"]).json()["code"] == "duplicate_document"


def test_similar_invoice_with_one_line_read_differently(client, wh, supplier):
    first = upload(client, supplier=supplier.pk)
    process(client, first["id"])
    goods = [row[:] for row in GOODS]
    goods[3][2] = "Сифон для мийки пласт."  # одну строку распознало иначе, сумма та же
    copy = upload(client, rows("Видаткова накладна", goods), "b.xlsx")
    [twin] = copy["duplicates"]
    assert (twin["id"], twin["reasons"], twin["same_lines"], twin["lines"]) == (first["id"], ["similar"], 4, 5)


def test_other_supply_is_not_a_duplicate(client, wh, supplier):
    first = upload(client, supplier=supplier.pk)
    process(client, first["id"])
    other_goods = [[1, "MIX-2", "Змішувач для ванни", 1, 2100, 2100], [2, "SF-1", "Сифон для мийки", 2, 300, 600]]
    # тот же номер, но другой поставщик и другие товары
    other = upload(client, rows(goods=other_goods), "c.xlsx", supplier=SupplierFactory().pk)
    assert other["duplicates"] == []
    assert process(client, other["id"]).status_code == 200


def test_unprocessed_copy_is_shown_and_blocks_only_after_the_first_is_processed(client, wh, supplier):
    a = upload(client, supplier=supplier.pk)
    b = upload(client, rows("Видаткова накладна № 77"), "b.xlsx", supplier=supplier.pk)
    assert [(d["id"], d["processed"]) for d in b["duplicates"]] == [(a["id"], False)]
    assert process(client, b["id"]).status_code == 200
    assert process(client, a["id"]).json()["code"] == "duplicate_document"


def test_items_scanned_on_receiving_are_not_received_again(client, wh, supplier):
    ProductVariantFactory(code="MIX-1", barcode="4820000000011")
    ProductVariantFactory(code="EXTRA", barcode="4820000000028", variant_name="Прокладка")
    doc = upload(client, supplier=supplier.pk)
    scan = reverse("warehouse:inventorydocument-scan", args=[doc["id"]])
    for code in ("4820000000011", "4820000000011", "4820000000028"):
        assert client.post(scan, {"barcode": code, "warehouse": wh.pk}, format="json").status_code == 200

    report = process(client, doc["id"]).json()
    assert stock_of("MIX-1") == 2  # 2 отсканировано + 0 по строке, а не 4
    assert stock_of("PPR-20") == 10
    assert report["already_received"] == [{"row": 1, "qty": "2.000"}]
    assert [(x["name"], x["qty"]) for x in report["scanner_extra"]] == [("Прокладка", "1.000")]


def test_reverse_returns_stock_and_document_can_be_fixed_and_processed(client, wh, supplier):
    doc = upload(client, supplier=supplier.pk)
    process(client, doc["id"])
    url = reverse("warehouse:inventorydocument-reverse", args=[doc["id"]])

    resp = client.post(url, {"reason": "дубль"}, format="json")
    assert resp.status_code == 200, resp.json()
    body = resp.json()
    assert body["processed"] is False and body["extracted_data"]["reversals"][0]["reason"] == "дубль"
    for code in ("MIX-1", "PPR-20", "KR-12", "SF-1", "GS-1"):
        variant = ProductVariant.objects.get(code=code)
        assert variant.stock == 0 and stock.journal_balance(variant.pk) == 0
    assert StockMovement.objects.filter(inventory_document_id=doc["id"], movement_type="in_reversal").count() == 5

    assert client.post(url, {}, format="json").status_code == 400  # уже отменено
    assert process(client, doc["id"]).status_code == 200  # исправили — провели снова
    assert stock_of("MIX-1") == 2


def test_reverse_refused_when_goods_are_sold_or_reserved(client, wh, supplier):
    doc = upload(client, supplier=supplier.pk)
    process(client, doc["id"])
    stock.reserve([(ProductVariant.objects.get(code="MIX-1"), 1)])  # под заказ
    stock.write_off(ProductVariant.objects.get(code="PPR-20"), wh, 3)  # продано

    resp = client.post(reverse("warehouse:inventorydocument-reverse", args=[doc["id"]]), {}, format="json")
    assert resp.status_code == 400 and resp.json()["code"] == "insufficient_stock"
    assert "Змішувач для кухні" in resp.json()["detail"] and "Труба PPR 20мм" in resp.json()["detail"]
    assert not StockMovement.objects.filter(movement_type="in_reversal").exists()  # всё или ничего
    assert InventoryDocument.objects.get(pk=doc["id"]).processed is True


def test_other_seller_cannot_reverse(client, wh, supplier):
    doc = upload(client, supplier=supplier.pk)
    process(client, doc["id"])
    stranger = APIClient()
    stranger.force_authenticate(SellerFactory().user)
    assert stranger.post(reverse("warehouse:inventorydocument-reverse", args=[doc["id"]])).status_code == 404


@pytest.mark.django_db(transaction=True)
def test_two_copies_processed_at_the_same_moment(client, seller, wh, supplier):
    ids = [
        upload(client, supplier=supplier.pk)["id"],
        upload(client, rows("№ 77"), "b.xlsx", supplier=supplier.pk)["id"],
    ]
    results, barrier = [], threading.Barrier(2)

    def run(doc_id):
        try:
            barrier.wait()
            process_inventory_document(InventoryDocument.objects.get(pk=doc_id), wh, seller.user)
            results.append("ok")
        except DuplicateDocumentError:
            results.append("duplicate")
        except Exception as exc:  # noqa: BLE001 — любая другая ошибка видна в assert
            results.append(repr(exc))
        finally:
            connection.close()

    threads = [threading.Thread(target=run, args=(doc_id,)) for doc_id in ids]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["duplicate", "ok"]
    assert stock_of("MIX-1") == 2


def test_migration_fills_keys_for_documents_uploaded_before(client, wh, supplier):
    from importlib import import_module

    from django.apps import apps

    doc = upload(client, supplier=supplier.pk)
    InventoryDocument.objects.filter(pk=doc["id"]).update(number_key="", fingerprint="", lines_total=None)
    import_module("app.apps.warehouse.migrations.0018_invoice_duplicates").fill_duplicate_keys(apps, None)
    filled = InventoryDocument.objects.get(pk=doc["id"])
    assert (filled.number_key, len(filled.fingerprint), str(filled.lines_total)) == ("77", 64, "5065.00")
