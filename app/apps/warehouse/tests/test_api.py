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

def _invoice_file():
    wb = Workbook()
    ws = wb.active
    for row in [
        ["Видаткова накладна № 77 від 01.10.2026"], ["Постачальник: ТОВ Тест"], [],
        ["№", "Артикул", "Товар", "Кількість", "Од.", "Ціна", "Сума"],
        [1, "ABC-1", "Змішувач для кухні", 2, "шт", 1500.50, 3001],
        [2, "ABC-2", "Труба PPR 20мм", 12.5, "м", 45.2, 565],
        [3, "ABC-1", "Змішувач для кухні", 1, "шт", 1500.50, 1500.50],
    ]:
        ws.append(row)
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile("invoice.xlsx", buf.getvalue())


def test_upload_rejects_bad_extension(client):
    resp = client.post(reverse("warehouse:inventorydocument-list"),
                       {"document_type": "incoming", "file": SimpleUploadedFile("x.exe", b"MZ")}, format="multipart")
    assert resp.status_code == 400


def test_process_invoice_receives_all_rows_once(client, wh, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    supplier = SupplierFactory()
    up = client.post(reverse("warehouse:inventorydocument-list"),
                     {"document_type": "incoming", "supplier": supplier.pk, "file": _invoice_file()},
                     format="multipart")
    assert up.status_code == 201, up.json()
    doc_id = up.json()["id"]
    url = reverse("warehouse:inventorydocument-process", args=[doc_id])

    first = client.post(url, {}, format="json")
    assert first.status_code == 200, first.json()
    assert first.json()["received"] == 3

    total = sum(m.quantity for m in StockMovement.objects.filter(inventory_document_id=doc_id))
    assert total == Decimal("15.5")  # 2 + 12.5 + 1: повторная строка не потеряна
    assert stock.get_balance(ProductVariant.objects.filter(movements__inventory_document_id=doc_id).first(), wh) > 0

    # повторное проведение запрещено — остаток не удваивается
    second = client.post(url, {}, format="json")
    assert second.status_code == 400
    assert StockMovement.objects.filter(inventory_document_id=doc_id).count() == 3

    # новые товары из накладной скрыты из каталога
    assert not ProductVariant.objects.filter(movements__inventory_document_id=doc_id, available=True).exists()
