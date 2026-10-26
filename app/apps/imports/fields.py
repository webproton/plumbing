"""Поля импорта: синонимы колонок/тегов у разных поставщиков и разбор значений."""

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from html import unescape

from parsers.core.numbers import safe_float

# Наше поле → как его называют поставщики (сравнение без регистра, пробелов и знаков препинания).
FIELD_SYNONYMS = {
    "external_id": ["id", "ід", "external_id", "offer_id", "product_id", "item_id", "код позиції", "код позиции"],
    "sku": [
        "артикул",
        "арт",
        "sku",
        "article",
        "articul",
        "vendorcode",
        "vendor_code",
        "код",
        "код товару",
        "код товара",
        "модель",
        "model",
        "mpn",
        "partnumber",
    ],
    "barcode": ["штрихкод", "штрих-код", "штрих код", "barcode", "ean", "ean13", "gtin", "upc", "шк"],
    "name": [
        "назва",
        "название",
        "наименование",
        "найменування",
        "назва товару",
        "название товара",
        "наименование товара",
        "товар",
        "name",
        "name_ua",
        "title",
        "product",
        "product_name",
    ],
    "variant": ["варіант", "вариант", "модифікація", "модификация", "variant"],
    "group": ["код групи", "група товару", "группа товара", "код группы", "group_id", "group", "parent_id"],
    "brand": [
        "бренд",
        "виробник",
        "производитель",
        "торгова марка",
        "торговая марка",
        "тм",
        "vendor",
        "brand",
        "manufacturer",
    ],
    "category": ["категорія", "категория", "category", "група", "группа", "розділ", "раздел", "category_name"],
    "price": [
        "ціна",
        "цена",
        "ціна продажу",
        "цена продажи",
        "роздрібна ціна",
        "розничная цена",
        "роздріб",
        "розница",
        "ррц",
        "rrp",
        "price",
        "retail",
        "retail_price",
        "price_retail",
    ],
    "old_price": [
        "стара ціна",
        "старая цена",
        "ціна до знижки",
        "цена до скидки",
        "oldprice",
        "old_price",
        "price_old",
    ],
    "cost": [
        "закупівельна ціна",
        "закупочная цена",
        "закупка",
        "закупівля",
        "вхідна ціна",
        "входная цена",
        "собівартість",
        "себестоимость",
        "опт",
        "оптова ціна",
        "оптовая цена",
        "ціна опт",
        "цена опт",
        "дилерська ціна",
        "дилерская цена",
        "cost",
        "cost_price",
        "purchase_price",
        "price_opt",
        "priceopt",
        "opt_price",
        "wholesale",
        "wholesale_price",
        "dealer_price",
    ],
    "currency": ["валюта", "currency", "currencyid", "currency_id"],
    "quantity": [
        "кількість",
        "количество",
        "залишок",
        "остаток",
        "к-сть",
        "кол-во",
        "склад",
        "qty",
        "quantity",
        "stock",
        "stock_quantity",
        "quantity_in_stock",
        "count",
    ],
    "available": ["наявність", "наличие", "available", "availability", "in_stock", "instock"],
    "description": ["опис", "описание", "description", "description_ua"],
    "photos": [
        "фото",
        "зображення",
        "изображение",
        "изображения",
        "картинка",
        "photo",
        "photos",
        "image",
        "images",
        "picture",
        "pictures",
        "image_url",
    ],
    "url": ["посилання", "ссылка", "url", "link", "product_url"],
    "visible": ["показувати на сайті", "показывать на сайте", "видимість", "видимость", "опубліковано", "visible"],
}

_NORM = re.compile(r"[\s_\-.:,;*()\[\]/\\№#\"']+")


def norm_header(value) -> str:
    return _NORM.sub("", str(value or "").strip().lower().replace("ё", "е"))


_LOOKUP = {norm_header(s): field for field, names in FIELD_SYNONYMS.items() for s in names}


def detect_columns(headers, overrides: dict | None = None, fields=None) -> dict[str, int]:
    """
    Колонки таблицы → {наше поле: индекс}.
    1) явная настройка источника (overrides: поле → название колонки);
    2) точное совпадение с синонимом;
    3) заголовок начинается с синонима («Ціна, грн» → price), длинные синонимы приоритетнее.
    """
    normalized = [norm_header(h) for h in headers]
    result: dict[str, int] = {}
    used: set[int] = set()

    for field, header in (overrides or {}).items():
        target = norm_header(header)
        if target and target in normalized:
            idx = normalized.index(target)
            result[field] = idx
            used.add(idx)

    for idx, h in enumerate(normalized):
        field = _LOOKUP.get(h)
        if h and field and field not in result and idx not in used and (fields is None or field in fields):
            result[field] = idx
            used.add(idx)

    prefixes = sorted(_LOOKUP.items(), key=lambda kv: -len(kv[0]))
    for idx, h in enumerate(normalized):
        if not h or idx in used:
            continue
        for synonym, field in prefixes:
            if (
                len(synonym) >= 3
                and h.startswith(synonym)
                and field not in result
                and (fields is None or field in fields)
            ):
                result[field] = idx
                used.add(idx)
                break
    return result


def to_text(value, limit: int | None = None) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # артикул/штрихкод из Excel приходят как 4820000000001.0
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text[:limit] if limit else text


_CDATA = re.compile(r"<!\[CDATA\[(.*?)\]\]>", re.DOTALL)
_BREAKS = re.compile(r"<br\s*/?>|</(?:p|div|li|h[1-6]|tr)>", re.IGNORECASE)
_TAGS = re.compile(r"</?[a-zA-Z!][^>]*>")  # «тиск < 6 бар» — не тег


def to_plain_text(value, limit: int | None = None) -> str:
    """Описание поставщика → обычный текст: сайт показывает его как текст, а не HTML.

    Некоторые фиды кладут CDATA экранированным («&lt;![CDATA[…]]&gt;»), и после разбора XML он остаётся в тексте.
    """
    text = _CDATA.sub(r"\1", str(value or ""))
    text = unescape(_TAGS.sub("", _BREAKS.sub("\n", text))).replace("\xa0", " ")
    lines = (re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n"))
    text = re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()
    return text[:limit] if limit else text


def to_decimal(value, places: str = "0.0001") -> Decimal | None:
    if value is None or value == "":
        return None
    number = safe_float(value)
    if number is None:
        return None
    try:
        return Decimal(str(number)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


_QTY = re.compile(r"-?\d+(?:[.,]\d+)?")


def to_quantity(value) -> Decimal | None:
    """«12», «12,5», «>10», «більше 50 шт» → число; текст без цифр → None."""
    if value is None or value == "" or isinstance(value, bool):
        return None
    if isinstance(value, (int, float, Decimal)):
        return max(Decimal(str(value)), Decimal(0)).quantize(Decimal("0.001"))
    match = _QTY.search(str(value))
    if not match:
        return None
    return max(Decimal(match.group().replace(",", ".")), Decimal(0)).quantize(Decimal("0.001"))


_YES = {
    norm_header(v)
    for v in (
        "1",
        "так",
        "да",
        "yes",
        "y",
        "true",
        "є",
        "есть",
        "в наявності",
        "в наличии",
        "є в наявності",
        "instock",
        "in stock",
        "available",
        "available_now",
    )
}
_NO = {
    norm_header(v)
    for v in (
        "0",
        "ні",
        "нет",
        "no",
        "n",
        "false",
        "немає",
        "нема",
        "відсутній",
        "отсутствует",
        "немає в наявності",
        "нет в наличии",
        "outofstock",
        "out of stock",
        "not available",
    )
}


def to_bool(value) -> bool | None:
    """Да/нет из ячейки или атрибута (так/ні, true/false, + / -, «в наявності»). Непонятное → None."""
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value > 0
    raw = str(value).strip()
    if raw in ("+", "-"):
        return raw == "+"
    text = norm_header(raw)
    if not text:
        return None
    if text in _YES:
        return True
    if text in _NO:
        return False
    return None


_URL = re.compile(r"https?://[^\s,;|]+", re.IGNORECASE)


def to_urls(value) -> list[str]:
    """Ссылки на фото из ячейки: через запятую, точку с запятой, | или перевод строки."""
    if not value:
        return []
    if isinstance(value, (list, tuple)):
        return [u for v in value for u in to_urls(v)]
    seen, result = set(), []
    for url in _URL.findall(str(value)):
        if url not in seen:
            seen.add(url)
            result.append(url[:1000])
    return result
