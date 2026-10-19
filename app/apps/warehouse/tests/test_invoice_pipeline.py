"""Разбор накладных: проверка арифметики, разбор по содержимому, ручные колонки, профили, PDF/фото, ИИ."""

from io import BytesIO

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from openpyxl import Workbook
from rest_framework.test import APIClient

from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse.models import InventoryDocument, InvoiceColumnProfile
from app.apps.warehouse.services import VariantMatcher
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory
from parsers import ai, pipeline
from parsers.core.loader import NeedsAI, load_rows
from parsers.quality import assess

pytestmark = pytest.mark.django_db

# Накладная «как попало»: шапка с бессмысленными подписями, ниже — строки товаров
MESSY = [
    ["Накладна від Олега"],
    ["", "", "", "", ""],
    ["п", "що", "скільки", "по чому", "разом"],
    [1, "Змішувач для кухні", 2, 1250.5, 2501],
    [2, "Сифон для мийки", 3, 149.9, 449.7],
    ["", "Всього", "", "", 2950.7],
]


def _xlsx(rows, name="inv.xlsx"):
    wb = Workbook()
    for r in rows:
        wb.active.append(r)
    buf = BytesIO()
    wb.save(buf)
    return SimpleUploadedFile(name, buf.getvalue())


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def client(seller):
    WarehouseFactory(seller=seller, is_default=True)
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


def _upload(client, file, **extra):
    resp = client.post(
        reverse("warehouse:inventorydocument-list"),
        {"file": file, "document_type": "incoming", **extra},
        format="multipart",
    )
    assert resp.status_code == 201, resp.content
    return resp.json()


# ---------------------------------------------------------------------------
# Чистые функции
# ---------------------------------------------------------------------------


def test_quality_assess():
    good = [{"name": "A", "qty": 2, "price": 10, "total": 20}, {"name": "B", "qty": 3, "price": 33.33, "total": 99.99}]
    q = assess(good, {"total": 119.99})
    assert (q["verdict"], q["consistent"], q["sum_match"]) == ("ok", 2, True)
    assert assess(good, {"total": 143.99, "vat": 24})["sum_match"] is True  # итог с ПДВ
    bad = [{"name": "A", "qty": 1, "price": 478, "total": 6404}]
    assert assess(bad, {"total": 478})["verdict"] == "bad"
    assert assess([], {})["verdict"] == "empty"


def test_pipeline_keeps_good_parser_result_untouched():
    rows = [
        ["Видаткова накладна № 5"],
        ["№", "Товар", "Кількість", "Ціна", "Сума"],
        [1, "Кран кульовий 1/2", 2, 150, 300],
        ["Разом", "", "", "", 300],
    ]
    result = pipeline.parse_rows(rows)
    assert result["engine"] == "parser" and result["quality"]["verdict"] == "ok"


def test_pipeline_universal_rescues_messy_invoice():
    result = pipeline.parse_rows(MESSY)
    assert result["engine"] == "universal"
    assert [(i["name"], i["qty"], i["price"], i["total"]) for i in result["items"]] == [
        ("Змішувач для кухні", 2.0, 1250.5, 2501.0),
        ("Сифон для мийки", 3.0, 149.9, 449.7),
    ]
    assert result["columns"]["columns"]["qty"] == 2  # не «п» (номер позиции)


def test_pipeline_manual_columns_and_profiles():
    manual = pipeline.parse_rows(
        MESSY, columns={"header_row": 2, "columns": {"name": 1, "qty": 2, "price": 3, "total": 4}}
    )
    assert manual["engine"] == "manual" and len(manual["items"]) == 2

    # профиль узнаёт свою шапку, даже если строки сдвинуты
    signature = pipeline.header_signature(MESSY, 2, {"name": 1, "qty": 2, "price": 3})
    profile = {"id": 7, "header": signature, "columns": {"name": 1, "qty": 2, "price": 3, "total": 4}}
    shifted = [["Шапка"], ["ще рядок"], *MESSY]
    result = pipeline.parse_rows(shifted, profiles=[profile])
    assert result["engine"] in ("profile", "universal") and len(result["items"]) == 2
    assert pipeline._profile_start(shifted, profile) == 5


def test_pipeline_ai_result_competes():
    ai_items = [
        {"position": 1, "name": "Змішувач", "qty": 2.0, "price": 1250.5, "total": 2501.0, "sku": "", "barcode": ""}
    ]
    broken = [["щось"], ["незрозуміле", "без", "чисел"]]
    result = pipeline.parse_rows(broken, ai_result={"items": ai_items, "meta": {"number": "AI-1"}, "totals": {}})
    assert result["engine"] == "ai" and result["meta"]["number"] == "AI-1"
    good = [["№", "Товар", "Кількість", "Ціна", "Сума"], [1, "Кран кульовий", 2, 150, 300]]
    assert pipeline.parse_rows(good, ai_result={"items": ai_items, "totals": {}})["engine"] == "parser"


def test_pdf_and_images(tmp_path):
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas
    from reportlab.platypus import SimpleDocTemplate, Table

    from config.settings import BASE_DIR

    pdfmetrics.registerFont(TTFont("UA", str(BASE_DIR / "app" / "fonts" / "DejaVuSans-Bold.ttf")))
    path = tmp_path / "inv.pdf"
    table = Table([["Товар", "Кількість", "Ціна", "Сума"], ["Змішувач кухонний", "2", "1250,50", "2501,00"]])
    table.setStyle([("FONTNAME", (0, 0), (-1, -1), "UA"), ("GRID", (0, 0), (-1, -1), 0.5, "black")])
    SimpleDocTemplate(str(path), pagesize=A4).build([table])
    result = pipeline.parse_rows(load_rows(str(path)))
    assert [(i["name"], i["qty"], i["price"]) for i in result["items"]] == [("Змішувач кухонний", 2.0, 1250.5)]

    scan = tmp_path / "scan.pdf"
    c = canvas.Canvas(str(scan))
    c.rect(10, 10, 100, 100, fill=1)
    c.save()
    with pytest.raises(NeedsAI):
        load_rows(str(scan))
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"\xff\xd8\xff")
    with pytest.raises(NeedsAI):
        load_rows(str(photo))


def test_matcher_tolerates_lookalike_letters():
    v1 = ProductVariantFactory(code="CN2N0160T", variant_name="Сидіння Титан")
    v2 = ProductVariantFactory(code="X-1", variant_name="Змішувач для кухні Grohe")
    matcher = VariantMatcher()
    assert matcher.match({"sku": "СN2N0160 Т", "name": "що завгодно"})[1] == v1.pk  # кириллические С и Т
    status, vid, method, *_ = matcher.match({"sku": "", "name": "Змiшувач для кухнi Grohe"})  # латинская i
    assert vid == v2.pk and method == "fuzzy"


# ---------------------------------------------------------------------------
# API накладных
# ---------------------------------------------------------------------------


def test_upload_messy_xlsx_is_parsed_by_content(client):
    doc = _upload(client, _xlsx(MESSY))
    data = doc["extracted_data"]
    assert data["engine"] == "universal" and data["quality"]["verdict"] in ("ok", "warning")
    assert [ln["status"] for ln in data["lines"]] == ["new", "new"]
    assert doc["ai"] == {"enabled": False, "status": "", "error": "", "has_result": False}


def test_photo_without_ai_explains(client):
    doc = _upload(client, SimpleUploadedFile("scan.jpg", b"\xff\xd8\xff\xe0", content_type="image/jpeg"))
    assert doc["extracted_data"]["code"] == "needs_ai"
    resp = client.post(reverse("warehouse:inventorydocument-ai", args=[doc["id"]]))
    assert resp.status_code == 400  # ИИ выключен


def test_table_and_manual_columns_with_profile(client):
    supplier = SupplierFactory()
    doc = _upload(client, _xlsx(MESSY), supplier=supplier.pk)
    table = client.get(reverse("warehouse:inventorydocument-table", args=[doc["id"]])).json()
    assert table["columns"] == [0, 1, 2, 3, 4] and table["suggested"]["columns"]["name"] == 1
    assert table["rows"][0] == {"index": 0, "cells": ["Накладна від Олега", "", "", "", ""]}

    url = reverse("warehouse:inventorydocument-columns", args=[doc["id"]])
    bad = client.post(url, {"columns": {"name": 1, "qty": 1, "price": 3}}, format="json")
    assert bad.status_code == 400
    resp = client.post(
        url,
        {"header_row": 2, "columns": {"name": 1, "qty": 2, "price": 3, "total": 4}, "remember": True},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    assert resp.json()["extracted_data"]["engine"] == "manual"
    profile = InvoiceColumnProfile.objects.get(supplier=supplier)
    assert profile.header == {"1": "що", "2": "скільки", "3": "по чому", "4": "разом"}

    # следующая накладная того же поставщика, другие строки — профиль узнаёт шапку
    other = [["Інша накладна"], ["п", "що", "скільки", "по чому", "разом"], [1, "Кран кульовий", 5, 100, 500]]
    doc2 = _upload(client, _xlsx(other, "inv2.xlsx"), supplier=supplier.pk)
    assert len(doc2["extracted_data"]["lines"]) == 1

    # без ручных колонок накладная разбирается запомненным профилем поставщика
    reset = client.post(url, {"reset": True}, format="json").json()
    assert reset["column_map"] is None and reset["extracted_data"]["engine"] == "profile"


@override_settings(INVOICE_AI_MODE="manual", ANTHROPIC_API_KEY="test-key")
def test_ai_parse_flow(client, monkeypatch):
    calls = []

    def fake_claude(content, *, api_key, model):
        calls.append(content)
        data = {
            "document_number": "77",
            "document_date": "2026-10-12",
            "items": [
                {"name": "Змішувач для кухні", "sku": "Z-1", "qty": 2, "unit": "шт", "price": 1250.5, "total": 2501}
            ],
            "total": 2501,
        }
        return data, {"input_tokens": 100, "output_tokens": 50}

    monkeypatch.setattr(ai, "call_claude", fake_claude)
    doc = _upload(client, SimpleUploadedFile("scan.png", b"\x89PNG\r\n\x1a\n", content_type="image/png"))
    assert doc["ai"]["enabled"] is True and doc["extracted_data"]["code"] == "needs_ai"

    resp = client.post(reverse("warehouse:inventorydocument-ai", args=[doc["id"]]))
    assert resp.status_code == 202
    document = InventoryDocument.objects.get(pk=doc["id"])
    assert document.ai_status == "done" and document.ai_result["usage"]["output_tokens"] == 50
    assert document.extracted_data["engine"] == "ai"
    assert [(ln["name"], ln["qty"], ln["price"]) for ln in document.extracted_data["lines"]] == [
        ("Змішувач для кухні", "2.000", "1250.5000")
    ]
    assert document.document_number == "77"
    assert calls[0][0]["type"] == "image"

    def failing(content, *, api_key, model):
        raise ai.AIError("Claude API: 529")

    monkeypatch.setattr(ai, "call_claude", failing)
    doc2 = _upload(client, _xlsx(MESSY, "m.xlsx"))
    client.post(reverse("warehouse:inventorydocument-ai", args=[doc2["id"]]))
    document2 = InventoryDocument.objects.get(pk=doc2["id"])
    assert document2.ai_status == "failed" and "529" in document2.ai_error
    assert document2.extracted_data["engine"] == "universal"  # прежний разбор не потерян


@override_settings(INVOICE_AI_MODE="auto", ANTHROPIC_API_KEY="test-key")
def test_ai_auto_mode_runs_for_scans_only(client, monkeypatch):
    calls = []
    monkeypatch.setattr(
        ai,
        "call_claude",
        lambda content, **kw: (calls.append(1), ({"items": []}, {"input_tokens": 1, "output_tokens": 1}))[1],
    )
    _upload(client, SimpleUploadedFile("scan.webp", b"RIFF0000WEBP", content_type="image/webp"))
    good = [["№", "Товар", "Кількість", "Ціна", "Сума"], [1, "Кран кульовий", 2, 150, 300]]
    _upload(client, _xlsx(good, "good.xlsx"))
    assert len(calls) == 1  # хорошая накладная в ИИ не отправляется
