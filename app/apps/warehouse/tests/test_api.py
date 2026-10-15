from decimal import Decimal
from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.models import InventoryDocument, StockMovement
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db


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
def stocked(wh):
    variant = ProductVariantFactory(barcode="4820000000011", code="SKU-1")
    stock.receive(variant, wh, 10, supplier=SupplierFactory())
    return variant


# --- права --------------------------------------------------------------

@pytest.mark.parametrize("url_name", ["warehouse:scanner_find", "warehouse:scanner_create"])
def test_scanner_requires_auth(url_name):
    resp = APIClient().post(reverse(url_name), {"query": "x"}, format="json")
    assert resp.status_code in (401, 403)


def test_unapproved_seller_has_no_access():
    seller = SellerFactory(is_approved=False)
    c = APIClient()
    c.force_authenticate(seller.user)
    assert c.get(reverse("warehouse:stock-movements-list")).status_code == 403


def test_regular_user_has_no_access():
    c = APIClient()
    c.force_authenticate(UserFactory())
    assert c.get(reverse("warehouse:warehouse-list")).status_code == 403


def test_seller_sees_only_own_movements(client, stocked):
    other_wh = WarehouseFactory()
    stock.receive(ProductVariantFactory(), other_wh, 1, supplier=SupplierFactory())
    data = client.get(reverse("warehouse:stock-movements-list")).json()
    rows = data["results"] if isinstance(data, dict) else data
    assert len(rows) == 1


# --- журнал неизменяем --------------------------------------------------

def test_journal_cannot_be_edited_or_deleted(client, stocked):
    mv = StockMovement.objects.get(variant=stocked)
    url = reverse("warehouse:stock-movements-detail", args=[mv.pk])
    assert client.put(url, {"quantity": 999}, format="json").status_code == 405
    assert client.patch(url, {"quantity": 999}, format="json").status_code == 405
    assert client.delete(url).status_code == 405


def test_manual_write_off_and_insufficient(client, wh, stocked):
    url = reverse("warehouse:stock-movements-list")
    ok = client.post(url, {"variant": stocked.pk, "warehouse": wh.pk, "movement_type": "out", "quantity": "2.5"},
                     format="json")
    assert ok.status_code == 201, ok.json()
    bad = client.post(url, {"variant": stocked.pk, "warehouse": wh.pk, "movement_type": "out", "quantity": 100},
                      format="json")
    assert bad.status_code == 400
    assert bad.json()["code"] == "insufficient_stock"
    assert ProductVariant.objects.get(pk=stocked.pk).stock == Decimal("7.5")


# --- чужие склады -------------------------------------------------------

def test_transfer_to_foreign_warehouse_forbidden(client, wh, stocked):
    foreign = WarehouseFactory()
    resp = client.post(reverse("warehouse:stock-movements-transfer"),
                       {"variant": stocked.pk, "from_warehouse": wh.pk, "to_warehouse": foreign.pk, "quantity": 1},
                       format="json")
    assert resp.status_code == 403
    assert stock.get_balance(stocked, wh) == 10


def test_transfer_fractional(client, seller, wh, stocked):
    other = WarehouseFactory(seller=seller)
    resp = client.post(reverse("warehouse:stock-movements-transfer"),
                       {"variant": stocked.pk, "from_warehouse": wh.pk, "to_warehouse": other.pk, "quantity": "2.75"},
                       format="json")
    assert resp.status_code == 200
    assert stock.get_balance(stocked, other) == Decimal("2.75")


def test_inventory_endpoint(client, wh, stocked):
    resp = client.post(reverse("warehouse:stock-movements-inventory"),
                       {"variant": stocked.pk, "warehouse": wh.pk, "quantity": 8}, format="json")
    assert resp.status_code == 200 and resp.json()["changed"] is True
    assert ProductVariant.objects.get(pk=stocked.pk).stock == 8


# --- сканер -------------------------------------------------------------

def test_scanner_find(client, wh, stocked):
    resp = client.post(reverse("warehouse:scanner_find"), {"query": "sku-1"}, format="json")
    assert resp.status_code == 200
    body = resp.json()
    assert body["variant_id"] == stocked.pk
    assert Decimal(body["stock_current"]) == 10


def test_scanner_create_and_receive(client, wh):
    doc = InventoryDocument.objects.create(
        seller=wh.seller, document_type="incoming", supplier=SupplierFactory(),
        file=SimpleUploadedFile("a.xlsx", b"x"),
    )
    resp = client.post(reverse("warehouse:scanner_create"), {
        "barcode": "999000111", "name": "Сифон", "price": "250", "cost_price": "120.5",
        "document": doc.pk, "warehouse": wh.pk, "quantity": 3,
    }, format="json")
    assert resp.status_code == 201, resp.json()
    variant = ProductVariant.objects.get(barcode="999000111")
    assert variant.available is False
    assert variant.stock == 3
    # повторное создание с тем же штрихкодом — конфликт, а не дубль
    again = client.post(reverse("warehouse:scanner_create"), {"barcode": "999000111", "name": "Сифон"}, format="json")
    assert again.status_code == 409


# --- проведение накладной ----------------------------------------------

def _invoice_file(rows=None, name="invoice.xlsx"):
    wb = Workbook()
    ws = wb.active
    for row in rows or [
        ["Видаткова накладна № 77 від 01.10.2026"], ["Постачальник: ТОВ Тест"], [],
        ["№", "Артикул", "Товар", "Кількість", "Од.", "Ціна", "Сума"],
        [1, "ABC-1", "Змішувач для кухні", 2, "шт", "1 500,50", "3 001,00"],
        [2, "PPR-20", "Труба PPR 20мм", 0.5, "м", 45.2, 22.6],
        [3, "ABC-1", "Змішувач для кухні", 1, "шт", 1500.50, 1500.50],
    ]:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(name, buf.getvalue())


def _upload(client, **extra):
    data = {"document_type": "incoming", "file": _invoice_file()}
    data.update(extra)
    return client.post(reverse("warehouse:inventorydocument-list"), data, format="multipart")


def test_upload_rejects_bad_extension(client):
    resp = client.post(reverse("warehouse:inventorydocument-list"),
                       {"document_type": "incoming", "file": SimpleUploadedFile("x.exe", b"MZ")}, format="multipart")
    assert resp.status_code == 400


def test_upload_parses_lines(client):
    resp = _upload(client, supplier=SupplierFactory().pk)
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["summary"] == {"matched": 0, "needs_review": 0, "new": 3, "invalid": 0}
    lines = data["extracted_data"]["lines"]
    assert [ln["sku"] for ln in lines] == ["ABC-1", "PPR-20", "ABC-1"]
    assert lines[1]["qty"] == "0.500"


def test_same_file_cannot_be_uploaded_twice(client):
    content = _invoice_file().read()
    assert _upload(client, file=SimpleUploadedFile("a.xlsx", content)).status_code == 201
    second = _upload(client, file=SimpleUploadedFile("копия.xlsx", content))
    assert second.status_code == 400
    assert "уже загружен" in str(second.json())


def test_process_invoice_receives_all_rows_once(client, wh):
    doc_id = _upload(client, supplier=SupplierFactory().pk).json()["id"]
    url = reverse("warehouse:inventorydocument-process", args=[doc_id])

    first = client.post(url, {}, format="json")
    assert first.status_code == 200, first.json()
    assert first.json()["received"] == 3

    total = sum(m.quantity for m in StockMovement.objects.filter(inventory_document_id=doc_id))
    assert total == Decimal("3.5")  # 2 + 0.5 + 1: повторная строка не потеряна, дробное кол-во сохранено

    # одинаковые строки (ABC-1 дважды) → один товар: вторая строка сопоставилась через память/артикул
    assert ProductVariant.objects.filter(movements__inventory_document_id=doc_id).distinct().count() == 2

    second = client.post(url, {}, format="json")
    assert second.status_code == 400
    assert StockMovement.objects.filter(inventory_document_id=doc_id).count() == 3
    assert not ProductVariant.objects.filter(movements__inventory_document_id=doc_id, available=True).exists()


def test_fuzzy_match_requires_review(client, wh):
    existing = ProductVariantFactory(variant_name="Змішувач для кухні Grohe Eurosmart", code="GROHE-1")
    rows = [
        ["№", "Артикул", "Товар", "Кількість", "Ціна", "Сума"],
        [1, "", "Змішувач для кухні Grohe Eurosmart хром", 1, 100, 100],
    ]
    up = client.post(reverse("warehouse:inventorydocument-list"),
                     {"document_type": "incoming", "supplier": SupplierFactory().pk, "file": _invoice_file(rows)},
                     format="multipart").json()
    line = up["extracted_data"]["lines"][0]
    assert line["status"] == "needs_review" and line["variant_id"] == existing.pk

    process_url = reverse("warehouse:inventorydocument-process", args=[up["id"]])
    blocked = client.post(process_url, {}, format="json")
    assert blocked.status_code == 400 and blocked.json()["code"] == "review_required"

    confirm = client.post(reverse("warehouse:inventorydocument-set-line", args=[up["id"], 1]),
                          {"variant": existing.pk}, format="json")
    assert confirm.status_code == 200 and confirm.json()["status"] == "matched"
    assert client.post(process_url, {}, format="json").status_code == 200
    assert ProductVariant.objects.get(pk=existing.pk).stock == 1


def test_duplicate_document_number_blocked(client, wh):
    supplier = SupplierFactory()
    first = _upload(client, supplier=supplier.pk).json()["id"]
    client.post(reverse("warehouse:inventorydocument-process", args=[first]), {}, format="json")
    rows = [["Видаткова накладна № 77"], ["№", "Артикул", "Товар", "Кількість", "Ціна", "Сума"],
            [1, "X-1", "Кран кульовий", 3, 10, 30]]
    second = client.post(reverse("warehouse:inventorydocument-list"),
                         {"document_type": "incoming", "supplier": supplier.pk, "file": _invoice_file(rows, "b.xlsx")},
                         format="multipart").json()["id"]
    resp = client.post(reverse("warehouse:inventorydocument-process", args=[second]), {}, format="json")
    assert resp.status_code == 400 and resp.json()["code"] == "duplicate_document"


def test_invoice_file_is_private(client):
    doc = InventoryDocument.objects.get(pk=_upload(client).json()["id"])
    from django.conf import settings
    assert str(settings.PRIVATE_MEDIA_ROOT) in doc.file.path
    resp = client.get(reverse("warehouse:inventorydocument-file", args=[doc.pk]))
    assert resp.status_code == 200
