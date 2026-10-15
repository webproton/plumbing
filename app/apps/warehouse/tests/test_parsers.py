"""Парсеры накладных на синтетических файлах."""

from pathlib import Path

import pytest
from openpyxl import Workbook

from parsers.core.loader import load_rows
from parsers.core.numbers import safe_float
from parsers.registry import parse


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1234.5", 1234.5),
        ("1234,5", 1234.5),
        ("1 234,50", 1234.5),
        ("1 234,50", 1234.5),
        ("1.234,50", 1234.5),
        ("1,234.50", 1234.5),
        ("12,5 грн", 12.5),
        ("45.20 USD", 45.2),
        ("0,5", 0.5),
        (7, 7.0),
        ("Труба 20мм", None),
        ("ABC-1", None),
        ("", None),
        (None, None),
        ("—", None),
    ],
)
def test_safe_float(raw, expected):
    assert safe_float(raw) == expected


def _xlsx(tmp_path, rows) -> Path:
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    path = tmp_path / "invoice.xlsx"
    wb.save(path)
    return path


def test_default_parser_uses_header_columns(tmp_path):
    path = _xlsx(
        tmp_path,
        [
            ["Видаткова накладна № 15 від 02.10.2026"],
            [],
            ["№", "Артикул", "Штрихкод", "Товар", "Кількість", "Од.", "Ціна", "Сума"],
            [1, "ABC-1", 4820000000011, "Змішувач Grohe", 2, "шт", "1 500,50", "3 001,00"],
            [2, "PPR-20", "", "Труба PPR 20мм", 0.5, "м", 45.2, 22.6],
            [],
            ["Всього", "", "", "", "", "", "", 3023.6],
        ],
    )
    result = parse(load_rows(str(path)))
    items = result["items"]
    assert result["meta"]["number"] == "15"
    assert [(i["sku"], i["barcode"], i["name"], i["qty"]) for i in items] == [
        ("ABC-1", "4820000000011", "Змішувач Grohe", 2.0),
        ("PPR-20", "", "Труба PPR 20мм", 0.5),
    ]
    assert items[0]["price"] == 1500.5


def test_yml_price_list_has_no_quantities(tmp_path):
    path = tmp_path / "price.yml"
    path.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<yml_catalog date="2026-10-01"><shop><name>Секвоя</name><company>ТОВ Секвоя</company>'
        '<categories><category id="1">Крани</category></categories>'
        '<offers><offer id="77"><name>Кран кульовий 1/2</name><price>120.50</price>'
        "<currencyId>UAH</currencyId><categoryId>1</categoryId></offer></offers></shop></yml_catalog>",
        encoding="utf-8",
    )
    rows = load_rows(str(path))
    header = rows.index(["Номенклатура (Товар)", "Артикул", "Кількість", "Ціна", "Од. вим.", "Категорія"])
    assert rows[header + 1][:3] == ["Кран кульовий 1/2", "77", ""]  # SKU из id, количества нет


def test_xml_external_entities_rejected(tmp_path):
    path = tmp_path / "evil.xml"
    path.write_text('<?xml version="1.0"?><!DOCTYPE r [<!ENTITY x SYSTEM "file:///etc/passwd">]><r>&x;</r>')
    with pytest.raises(ValueError):
        load_rows(str(path))
