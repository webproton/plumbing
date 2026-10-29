"""
Разбор каталога поставщика в единый вид (SourceItem).

Поддерживается: YML (Prom.ua / Rozetka / Hotline), произвольный XML, CSV, Excel (xlsx/xls), JSON.
Колонки и теги распознаются по синонимам (fields.FIELD_SYNONYMS), а то, что не распозналось,
настраивается в источнике: field_map = {"price": "Ціна роздріб", "sku": "Код"}.
"""

import csv
import hashlib
import io
import json
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from functools import partial

from defusedxml import ElementTree as ET
from django.utils.translation import gettext as _

from .fields import detect_columns, to_bool, to_decimal, to_plain_text, to_quantity, to_text, to_urls

MAX_ITEMS = 100_000
HEADER_SCAN_ROWS = 30
MAX_PARAMS = 40


class FormatError(Exception):
    pass


@dataclass
class SourceItem:
    external_id: str
    name: str = ""
    sku: str = ""
    barcode: str = ""
    brand: str = ""
    category: str = ""
    description: str = ""
    url: str = ""
    price: Decimal | None = None
    old_price: Decimal | None = None
    cost: Decimal | None = None
    currency: str = ""
    cost_currency: str = ""  # если закупка в другой валюте, чем цена (у Секвои: опт в $, РРЦ в грн)
    quantity: Decimal | None = None
    available: bool | None = None
    photos: list = field(default_factory=list)
    params: dict = field(default_factory=dict)

    def digest(self) -> str:
        return hashlib.sha256(json.dumps(asdict(self), default=str, sort_keys=True).encode()).hexdigest()


@dataclass
class ParsedTable:
    """Строки таблицы после распознавания колонок: (номер строки в файле, {поле: значение}, {прочие колонки})."""

    rows: list
    columns: dict  # поле → заголовок колонки
    header_row: int


# ---------------------------------------------------------------------------
# Определение формата
# ---------------------------------------------------------------------------


def detect_format(content: bytes, filename: str = "") -> str:
    name = filename.lower()
    head = content[:4096].lstrip(b"\xef\xbb\xbf \t\r\n")
    if content[:4] == b"PK\x03\x04" or content[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return "xlsx"
    if head.startswith(b"<"):
        return "yml" if b"<yml_catalog" in content[:4096] else "xml"
    if head[:1] in (b"{", b"["):
        return "json"
    if name.endswith((".xlsx", ".xls")):
        return "xlsx"
    return "csv"


def parse_items(content: bytes, fmt: str = "auto", field_map: dict | None = None, options: dict | None = None):
    """→ (items, info). info: формат, распознанные колонки, сколько строк пропущено."""
    options = options or {}
    fmt = detect_format(content, options.get("filename", "")) if fmt in ("", "auto") else fmt
    if fmt == "yml":
        items, info = _parse_yml(content, field_map or {})
    elif fmt == "xml":
        items, info = parse_records(_xml_records(content, options.get("items_tag", "")), field_map or {})
    elif fmt == "json":
        items, info = parse_records(json_records(content, options.get("items_path", "")), field_map or {})
    elif fmt in ("csv", "xlsx"):
        table = read_table(content, fmt, field_map or {}, options)
        items, skipped = [], 0
        for _row, values, extra in table.rows:
            item = build_item(values, extra)
            if item:
                items.append(item)
            else:
                skipped += 1
        info = {"columns": table.columns, "skipped": skipped}
    else:
        raise FormatError(_("Неизвестный формат: {fmt}").format(fmt=fmt))
    info["format"] = fmt
    return dedupe(items, info), info


def dedupe(items, info):
    by_id = {}
    for item in items:
        by_id[item.external_id] = item
    info["duplicates"] = len(items) - len(by_id)
    if len(by_id) > MAX_ITEMS:
        raise FormatError(_("Слишком много товаров в файле (больше {max})").format(max=MAX_ITEMS))
    return list(by_id.values())


# ---------------------------------------------------------------------------
# Единый товар из распознанных значений
# ---------------------------------------------------------------------------


def build_item(values: dict, params: dict | None = None) -> SourceItem | None:
    sku = to_text(values.get("sku"), 100)
    barcode = re.sub(r"\s+", "", to_text(values.get("barcode"), 50))
    name = to_text(values.get("name"), 500)
    external_id = to_text(values.get("external_id"), 255) or sku or barcode
    if not external_id:
        if not name:
            return None
        external_id = "name:" + hashlib.sha1(name.lower().encode()).hexdigest()[:20]

    quantity = to_quantity(values.get("quantity"))
    available = to_bool(values.get("available"))
    if available is None and quantity is None and values.get("available") not in (None, ""):
        quantity = to_quantity(values.get("available"))  # «Наявність: 15»
    if available is None and quantity is not None:
        available = quantity > 0

    return SourceItem(
        external_id=external_id,
        name=name,
        sku=sku,
        barcode=barcode,
        brand=to_text(values.get("brand"), 255),
        category=to_text(values.get("category"), 255),
        description=to_plain_text(values.get("description"), 20000),
        url=to_text(values.get("url"), 1000),
        price=to_decimal(values.get("price")),
        old_price=to_decimal(values.get("old_price")),
        cost=to_decimal(values.get("cost")),
        currency=_currency(values.get("currency")),
        cost_currency=_currency(values.get("cost_currency")),
        quantity=quantity,
        available=available,
        photos=to_urls(values.get("photos"))[:20],
        params={k: to_text(v, 500) for k, v in list((params or {}).items())[:MAX_PARAMS] if to_text(v)},
    )


_CURRENCY_SIGNS = {"$": "USD", "ДОЛ": "USD", "€": "EUR", "ЄВРО": "EUR", "ЕВРО": "EUR", "ГРН": "UAH", "₴": "UAH"}


def _currency(value) -> str:
    """«$» → USD, «грн.» → UAH: прайсы пишут валюту как угодно, курсы в админке — по кодам."""
    code = to_text(value, 10).strip().upper().rstrip(".")
    return _CURRENCY_SIGNS.get(code, code)[:3]


# ---------------------------------------------------------------------------
# Таблицы (CSV / Excel)
# ---------------------------------------------------------------------------


def _decode(content: bytes, encoding: str = "") -> str:
    for enc in [e for e in (encoding, "utf-8-sig", "cp1251") if e]:
        try:
            return content.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return content.decode("utf-8", errors="replace")


def _csv_rows(content: bytes, options: dict) -> list[list]:
    text = _decode(content, options.get("encoding", ""))
    delimiter = options.get("delimiter") or ""
    if not delimiter:
        try:
            delimiter = csv.Sniffer().sniff(text[:8192], delimiters=";,\t|").delimiter
        except csv.Error:
            delimiter = ";" if text[:2048].count(";") > text[:2048].count(",") else ","
    return [row for row in csv.reader(io.StringIO(text), delimiter=delimiter)]


def _excel_rows(content: bytes, options: dict) -> list[list]:
    sheet = options.get("sheet") or None
    if content[:4] == b"PK\x03\x04":
        from openpyxl import load_workbook

        try:
            wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            ws = wb[sheet] if sheet and sheet in wb.sheetnames else wb.worksheets[0]
            return [list(r) for r in ws.iter_rows(values_only=True)]
        except Exception:  # noqa: BLE001 — битый xlsx пробуем прочитать вторым движком
            pass
    import pandas as pd

    try:
        df = pd.read_excel(io.BytesIO(content), header=None, engine="calamine", sheet_name=sheet or 0, dtype=object)
    except Exception as exc:  # noqa: BLE001
        raise FormatError(_("Не удалось прочитать Excel-файл")) from exc
    return df.where(df.notna(), None).values.tolist()


def read_table(content: bytes, fmt: str, field_map: dict, options: dict | None = None) -> ParsedTable:
    options = options or {}
    rows = _excel_rows(content, options) if fmt == "xlsx" else _csv_rows(content, options)
    if not rows:
        raise FormatError(_("Файл пустой"))

    best, best_idx = {}, -1
    for idx, row in enumerate(rows[:HEADER_SCAN_ROWS]):
        columns = detect_columns(row, field_map)
        if ("name" in columns or "sku" in columns) and len(columns) > len(best):
            best, best_idx = columns, idx
    if best_idx < 0 or len(best) < 2:
        raise FormatError(_("Не найдена строка заголовков: нужны хотя бы колонки «Название» или «Артикул» и «Цена»"))

    header = rows[best_idx]
    known = set(best.values())
    extra_cols = [(i, to_text(h, 100)) for i, h in enumerate(header) if i not in known and to_text(h)]
    parsed, group = [], ""
    for offset, row in enumerate(rows[best_idx + 1 :], start=best_idx + 2):
        filled = [c for c in row if to_text(c)]
        if not filled:
            continue
        values = {f: (row[i] if i < len(row) else None) for f, i in best.items()}
        if len(filled) == 1 and not to_text(values.get("price")) and not to_text(values.get("sku")):
            group = to_text(filled[0], 255)  # строка-группа прайса 1С — не товар
            continue
        if group and "category" not in best:
            values["category"] = group
        extra = {h: row[i] for i, h in extra_cols if i < len(row) and to_text(row[i])}
        parsed.append((offset, values, extra))
    return ParsedTable(rows=parsed, columns={f: to_text(header[i]) for f, i in best.items()}, header_row=best_idx + 1)


# ---------------------------------------------------------------------------
# Записи-словари (XML / JSON): ключ → значение
# ---------------------------------------------------------------------------


def parse_records(records: list[dict], field_map: dict):
    keys = list(dict.fromkeys(k for record in records[:200] for k in record))
    columns = detect_columns(keys, field_map)
    if "name" not in columns and "sku" not in columns:
        raise FormatError(_("Не найдены поля с названием или артикулом товара — настройте соответствие полей"))
    mapped = {f: keys[i] for f, i in columns.items()}
    by_lower = {k.lower(): k for k in keys}
    for field, currency_field in (("price", "currency"), ("cost", "cost_currency")):
        attr_key = by_lower.get(f"{mapped.get(field, '')}@currency".lower())
        if field in mapped and currency_field not in mapped and attr_key:
            mapped[currency_field] = attr_key
    known = set(mapped.values())
    items, skipped = [], 0
    for record in records:
        values = {f: record.get(k) for f, k in mapped.items()}
        extra = {k: v for k, v in record.items() if k not in known and not isinstance(v, (list, dict))}
        item = build_item(values, extra)
        if item:
            items.append(item)
        else:
            skipped += 1
    return items, {"columns": mapped, "skipped": skipped}


def _flatten(obj, prefix=""):
    out = {}
    for key, value in obj.items():
        path = f"{prefix}{key}"
        if isinstance(value, dict):
            out.update(_flatten(value, f"{path}."))
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            continue  # вложенные списки объектов (варианты, склады) — только через field_map на верхний уровень
        else:
            out[path] = value
    return out


def _dig(obj, path: str):
    for part in [p for p in path.split(".") if p]:
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit() and int(part) < len(obj):
            obj = obj[int(part)]
        else:
            return None
    return obj


def json_records(content: bytes | str | list | dict, items_path: str = "") -> list[dict]:
    if isinstance(content, (bytes, str)):
        try:
            data = json.loads(_decode(content) if isinstance(content, bytes) else content)
        except ValueError as exc:
            raise FormatError(_("Некорректный JSON")) from exc
    else:
        data = content
    if items_path:
        data = _dig(data, items_path)
    elif isinstance(data, dict):
        # первый список объектов: {"data": [...]}, {"result": {"items": [...]}}
        candidates = [v for v in _flatten_lists(data) if v and all(isinstance(x, dict) for x in v)]
        data = max(candidates, key=len) if candidates else []
    if not isinstance(data, list):
        raise FormatError(_("В ответе не найден список товаров — укажите путь к списку (items_path)"))
    return [_flatten(x) for x in data if isinstance(x, dict)]


def _flatten_lists(obj, depth=0):
    if depth > 3 or not isinstance(obj, dict):
        return
    for value in obj.values():
        if isinstance(value, list):
            yield value
        elif isinstance(value, dict):
            yield from _flatten_lists(value, depth + 1)


def _xml_root(content: bytes):
    try:
        return ET.fromstring(content)
    except Exception as exc:  # noqa: BLE001 — defusedxml бросает разные исключения
        raise FormatError(_("Не удалось разобрать XML: {error}").format(error=exc)) from exc


def _local(tag) -> str:
    return str(tag).rsplit("}", 1)[-1]


def _xml_records(content: bytes, items_tag: str = "") -> list[dict]:
    root = _xml_root(content)
    if not items_tag:
        counts = Counter(_local(el.tag) for el in root.iter() if len(el) >= 2)
        counts.pop(_local(root.tag), None)
        if not counts:
            raise FormatError(_("В XML не найдены товары"))
        items_tag = counts.most_common(1)[0][0]
    records = []
    for el in root.iter():
        if _local(el.tag) != items_tag:
            continue
        record = {f"@{k}": v for k, v in el.attrib.items()}
        repeated = Counter(_local(child.tag) for child in el)
        for child in el:
            key = _local(child.tag)
            text = (child.text or "").strip()
            if repeated[key] > 1 and child.attrib:
                # <Price PriceType="РРЦ" Currency="UAH">15.6</Price> → «РРЦ»: 15.6, «РРЦ@Currency»: UAH
                kind = next(iter(child.attrib.values())).strip() or key
                record.setdefault(kind, text)
                for attr, value in child.attrib.items():
                    record.setdefault(f"{kind}@{attr}", value)
                continue
            if key in record:
                previous = record[key] if isinstance(record[key], list) else [record[key]]
                record[key] = [*previous, text]
            else:
                record[key] = text
            for attr, value in child.attrib.items():
                record.setdefault(f"{key}@{attr}", value)
        records.append(record)
    return records


# ---------------------------------------------------------------------------
# YML (Yandex Market Language): Prom.ua, Rozetka, Hotline, большинство B2B-выгрузок
# ---------------------------------------------------------------------------

_YML_COST_TAGS = ("purchase_price", "price_opt", "priceopt", "opt_price", "wholesale_price", "dealer_price", "price_in")
_YML_QTY_TAGS = ("quantity_in_stock", "stock_quantity", "quantity", "stock", "count")


def _first_text(node, *names) -> str:
    for name in names:
        child = node.find(name)
        if child is not None and (child.text or "").strip():
            return child.text.strip()
    return ""


def _parse_yml(content: bytes, field_map: dict):
    root = _xml_root(content)
    shop = root.find("shop")
    shop = shop if shop is not None else root
    categories = {c.get("id"): (c.text or "").strip() for c in shop.iter("category")}

    items, skipped = [], 0
    for offer in shop.iter("offer"):
        tag = partial(_first_text, offer)
        name = tag("name_ua", "name") or " ".join(p for p in (tag("typePrefix"), tag("vendor"), tag("model")) if p)
        params = {p.get("name"): (p.text or "").strip() for p in offer.findall("param") if p.get("name")}
        values = {
            "external_id": offer.get("id") or tag("vendorCode"),
            "name": name,
            "sku": tag("vendorCode", "article", "sku"),
            "barcode": tag("barcode", "ean"),
            "brand": tag("vendor", "brand"),
            "category": categories.get(tag("categoryId"), ""),
            "description": tag("description_ua", "description"),
            "url": tag("url"),
            "price": tag("price"),
            "old_price": tag("oldprice", "price_old"),
            "cost": tag(*_YML_COST_TAGS),
            "currency": tag("currencyId"),
            "quantity": tag(*_YML_QTY_TAGS),
            "available": offer.get("available", ""),
            "photos": [(p.text or "").strip() for p in offer.findall("picture")],
        }
        for our, source_tag in field_map.items():  # ручная настройка: тег или @атрибут
            values[our] = offer.get(source_tag[1:], "") if source_tag.startswith("@") else tag(source_tag)
        item = build_item(values, params)
        if item:
            items.append(item)
        else:
            skipped += 1
    if not items and not skipped:
        raise FormatError(_("В YML-файле нет товаров (<offer>)"))
    return items, {"columns": {}, "skipped": skipped, "categories": len(categories)}
