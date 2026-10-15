# parsers/normalizer.py
import re

from parsers.core.numbers import safe_float

_CURRENCY = re.compile(r"(грн|uah|₴|usd|\$|eur|€)", re.IGNORECASE)
_CURRENCY_CODES = {"грн": "UAH", "uah": "UAH", "₴": "UAH", "usd": "USD", "$": "USD", "eur": "EUR", "€": "EUR"}


def _barcode(value):
    if value in (None, ""):
        return ""
    text = str(value).strip()
    if re.fullmatch(r"\d+\.0+", text):  # Excel отдаёт EAN как float: 4820000000011.0
        text = text.split(".")[0]
    return re.sub(r"\D", "", text)


def normalize_item(item):
    """Приводит строку накладной к единому виду (регистр названия сохраняется)."""
    if not item or not isinstance(item, dict):
        return item

    item = dict(item)
    item["name"] = re.sub(r"\s+", " ", str(item.get("name") or "")).strip()
    item["sku"] = str(item.get("sku") or "").strip().upper()
    item["barcode"] = _barcode(item.get("barcode"))

    raw_price = item.get("price")
    match = _CURRENCY.search(str(raw_price or ""))
    if match and not item.get("currency"):
        item["currency"] = _CURRENCY_CODES[match.group(1).lower()]

    for key in ("qty", "price", "total"):
        if key in item:
            item[key] = safe_float(item[key])
    return item
