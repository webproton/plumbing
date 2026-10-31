import io
import json
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.apps.imports.fields import detect_columns, to_bool, to_plain_text, to_quantity
from app.apps.imports.formats import FormatError, detect_format, parse_items

YML = """<?xml version="1.0" encoding="UTF-8"?>
<yml_catalog date="2026-10-01 10:00">
 <shop>
  <currencies><currency id="UAH" rate="1"/></currencies>
  <categories><category id="10">Змішувачі</category><category id="11">Труби</category></categories>
  <offers>
   <offer id="A-1" available="true">
     <name>Змішувач для кухні</name><name_ua>Змішувач для кухні UA</name_ua>
     <price>2499.00</price><oldprice>2999</oldprice><price_opt>1700,50</price_opt>
     <currencyId>UAH</currencyId><categoryId>10</categoryId>
     <picture>https://cdn.example.com/a1.jpg</picture><picture>https://cdn.example.com/a2.jpg</picture>
     <vendor>Grohe</vendor><vendorCode>GR-100</vendorCode><barcode>4005176000001</barcode>
     <quantity_in_stock>7</quantity_in_stock>
     <param name="Колір">Хром</param>
     <description><![CDATA[<p>Опис</p>]]></description>
   </offer>
   <offer id="B-2" available="false">
     <name>Труба 20</name><price>55</price><categoryId>11</categoryId><vendorCode>TR-20</vendorCode>
   </offer>
  </offers>
 </shop>
</yml_catalog>""".encode()


def test_detect_format():
    assert detect_format(YML) == "yml"
    assert detect_format(b"<root><item><a>1</a><b>2</b></item></root>") == "xml"
    assert detect_format(b' [{"a": 1}]') == "json"
    assert detect_format(b"PK\x03\x04....") == "xlsx"
    assert detect_format("Артикул;Назва\n1;2".encode()) == "csv"


def test_yml_offer_fields():
    items, info = parse_items(YML)
    assert info["format"] == "yml"
    a, b = sorted(items, key=lambda i: i.external_id)
    assert a.external_id == "A-1" and a.name == "Змішувач для кухні UA"
    assert (a.sku, a.barcode, a.brand, a.category) == ("GR-100", "4005176000001", "Grohe", "Змішувачі")
    assert (a.price, a.old_price, a.cost) == (Decimal("2499.0000"), Decimal("2999.0000"), Decimal("1700.5000"))
    assert a.quantity == Decimal("7.000") and a.available is True
    assert a.photos == ["https://cdn.example.com/a1.jpg", "https://cdn.example.com/a2.jpg"]
    assert a.params == {"Колір": "Хром"} and a.description == "Опис"
    assert b.available is False and b.quantity is None


def test_yml_field_map_override_attribute():
    items, _info = parse_items(YML, "yml", {"sku": "@id"})
    assert {i.sku for i in items} == {"A-1", "B-2"}


def test_csv_semicolon_cp1251_and_header_detection():
    text = "Прайс-лист ТОВ Постачальник\n\nКод товару;Найменування;Ціна, грн;Ціна опт;Наявність\n"
    text += "K-1;Кран кульовий 1/2;150,50;99,9;є\nK-2;Кран 3/4;;;немає\n;;;;\nK-3;Без ціни;0;;>10\n"
    items, info = parse_items(text.encode("cp1251"), "csv")
    by_id = {i.external_id: i for i in items}
    assert info["columns"]["sku"] == "Код товару" and info["columns"]["cost"] == "Ціна опт"
    assert by_id["K-1"].price == Decimal("150.5000") and by_id["K-1"].available is True
    assert by_id["K-2"].available is False and by_id["K-2"].price is None
    assert by_id["K-3"].quantity == Decimal("10.000") and by_id["K-3"].available is True


def test_xlsx_with_title_rows_and_field_map():
    wb = Workbook()
    ws = wb.active
    ws.append(["Прайс на 01.10.2026"])
    ws.append([])
    ws.append(["Артикул", "Товар", "РРЦ", "Склад Київ", "Штрих-код"])
    ws.append(["X-1", "Унітаз", 5200, 3, 4820000000017])
    buf = io.BytesIO()
    wb.save(buf)
    items, info = parse_items(buf.getvalue(), "auto", {"quantity": "Склад Київ"})
    (item,) = items
    assert info["format"] == "xlsx"
    assert (item.sku, item.name, item.price, item.quantity) == ("X-1", "Унітаз", Decimal("5200.0000"), Decimal("3.000"))
    assert item.barcode == "4820000000017"  # без «.0» от Excel


def test_json_nested_items_and_dotted_map():
    payload = {"meta": {"page": 1}, "data": {"products": [
        {"id": 1, "article": "J-1", "title": "Сифон", "prices": {"retail": "320.5", "dealer": 200}, "stock": 4},
        {"id": 2, "article": "J-2", "title": "Гофра", "prices": {"retail": 80}, "stock": 0},
    ]}}  # fmt: skip
    items, info = parse_items(json.dumps(payload).encode(), "json", {"price": "prices.retail", "cost": "prices.dealer"})
    by_id = {i.external_id: i for i in items}
    assert by_id["1"].price == Decimal("320.5000") and by_id["1"].cost == Decimal("200.0000")
    assert by_id["2"].available is False
    assert info["columns"]["name"] == "title"


def test_generic_xml_autodetects_item_tag():
    xml = b"""<export><goods>
      <good code="G1"><title>Mixer</title><price>10</price><qty>2</qty></good>
      <good code="G2"><title>Pipe</title><price>3</price><qty>0</qty></good>
    </goods></export>"""
    items, _info = parse_items(xml, "xml", {"external_id": "@code"})
    assert sorted(i.external_id for i in items) == ["G1", "G2"]


def test_duplicates_are_merged_and_empty_rejected():
    items, info = parse_items("Артикул;Назва;Ціна\nA;1;10\nA;1 new;11\n".encode(), "csv")
    assert len(items) == 1 and items[0].name == "1 new" and info["duplicates"] == 1
    with pytest.raises(FormatError):
        parse_items("щось;інше\n1;2\n".encode(), "csv")
    with pytest.raises(FormatError):
        parse_items(b"<yml_catalog><shop><offers></offers></shop></yml_catalog>", "yml")


def test_xml_bomb_is_rejected():
    bomb = b'<?xml version="1.0"?><!DOCTYPE l [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]><r><i><n>&b;</n><p>1</p></i></r>'
    with pytest.raises(FormatError):
        parse_items(bomb, "xml")


def test_value_helpers():
    assert detect_columns(["Назва", "Ціна, грн", "Опт. ціна"])["price"] == 1
    assert to_bool("В наявності") is True and to_bool("нет в наличии") is False and to_bool("?") is None
    assert to_quantity("більше 50 шт") == Decimal("50.000") and to_quantity("немає") is None


def test_descriptions_become_plain_text():
    # O&L кладёт CDATA экранированным: после разбора XML в тексте остаётся «<![CDATA[…]]>»
    feed = YML.replace(
        "<description><![CDATA[<p>Опис</p>]]></description>".encode(),
        "<description>&lt;![CDATA[&lt;div&gt;2-ге місце&amp;nbsp;13 кг&lt;/div&gt;]]&gt;</description>".encode(),
    ).replace(b"<price>55</price>", b"<price>55</price><description>&lt;![CDATA[]]&gt;</description>")
    items, _info = parse_items(feed)
    a, b = sorted(items, key=lambda i: i.external_id)
    assert a.description == "2-ге місце 13 кг" and b.description == ""
    assert to_plain_text("<p>Тиск < 6 бар</p><ul><li>DN 15</li><li>DN 20</li></ul>") == "Тиск < 6 бар\nDN 15\nDN 20"
    assert to_plain_text("Рядок 1<br>Рядок 2") == "Рядок 1\nРядок 2"


SEQUOIA = """<?xml version="1.0" encoding="UTF-8"?>
<Catalog>
 <Product>
  <SKU>1003390</SKU><Article></Article><Brand>HOT RIGHT PPR пайка фітинг</Brand>
  <Thumbnail>https://b2b.example.com//gallery/product_gallery/a.webp</Thumbnail>
  <Name>Муфта  40 {360/15}</Name>
  <Price PriceType="Wholesale price" Currency="$" Rate="46.55">0.26</Price>
  <Price PriceType="РРЦ" Currency="UAH" Rate="1">15.600</Price>
  <Stock Branch="Дніпро">238</Stock>
 </Product>
 <Product>
  <SKU>1010071</SKU><Article></Article><Brand>STA кран</Brand><Thumbnail></Thumbnail>
  <Name>Кран кульовий 1/2</Name>
  <Price PriceType="Wholesale price" Currency="$" Rate="46.55">2.5</Price>
  <Price PriceType="РРЦ" Currency="UAH" Rate="1">150</Price>
 </Product>
</Catalog>"""


def test_xml_with_typed_prices_and_thumbnails():
    """Секвоя: две <Price> — опт в $ и РРЦ в грн (различаются атрибутом), фото — в <Thumbnail>."""
    items, info = parse_items(SEQUOIA.encode(), "auto")
    by_sku = {i.sku: i for i in items}
    first = by_sku["1003390"]
    assert (first.price, first.currency) == (Decimal("15.6000"), "UAH")
    assert (first.cost, first.cost_currency) == (Decimal("0.2600"), "USD")
    assert first.photos == ["https://b2b.example.com//gallery/product_gallery/a.webp"]
    assert first.quantity == Decimal("238")
    assert first.brand == "HOT RIGHT PPR пайка фітинг"
    assert by_sku["1010071"].photos == [] and by_sku["1010071"].price == Decimal("150")
    assert (info["columns"]["price"], info["columns"]["cost"]) == ("РРЦ", "Wholesale price")


def test_1c_price_list_with_group_rows():
    """Санвел (выгрузка 1С): служебные строки над шапкой, группы — отдельными строками, «Номенклатура», «Ваша ціна»."""
    wb = Workbook()
    ws = wb.active
    ws.append(["Постачальник:", "SanWell"])
    ws.append(["Вид прайс-листа:", "Прайс-лист із вашими цінами"])
    ws.append([])
    ws.append(["Група"])
    ws.append(["Номенклатура", "Код", "Ціна, РРЦ", "Ваша ціна", "Вал.", "Од.вим."])
    ws.append(["Системи очищення води"])
    ws.append(["Потрійний фільтр Ecosoft Standard", "45062", 2340.0, "1 800,000", "UAH", "шт"])
    ws.append(["Змішувачі"])
    ws.append(["Змішувач для кухні", "71001", 1500, "1 100,50", "грн", "шт"])
    buf = io.BytesIO()
    wb.save(buf)
    items, info = parse_items(buf.getvalue(), "xlsx")
    by_sku = {i.sku: i for i in items}
    water = by_sku["45062"]
    assert water.name == "Потрійний фільтр Ecosoft Standard"
    assert (water.price, water.cost, water.currency) == (Decimal("2340.0000"), Decimal("1800.0000"), "UAH")
    assert water.category == "Системи очищення води"
    assert (by_sku["71001"].category, by_sku["71001"].currency, by_sku["71001"].cost) == (
        "Змішувачі", "UAH", Decimal("1100.5000"))
    assert len(items) == 2 and info["columns"]["name"] == "Номенклатура"
