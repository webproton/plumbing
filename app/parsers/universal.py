"""
Универсальный разбор таблицы накладной ПО СОДЕРЖИМОМУ, без доверия к заголовкам.

Накладные составляют вручную, разные люди и каждый раз по-своему: колонки переставлены, подписаны
неправильно или не подписаны вовсе. Поэтому колонки определяются так:
  • количество / цена / сумма — тройка числовых колонок, для которой в строках выполняется кол-во × цена = сумма;
  • название — колонка с самым длинным текстом; единица — «шт», «м», «кг»…; штрихкод — числа из 8–14 цифр;
  • артикул — колонка с короткими кодами (не номер позиции 1, 2, 3…); заголовок «Код»/«Артикул» — подсказка.
Используется, когда основной парсер не сошёлся (см. pipeline.py), и для ручной настройки колонок.
"""

import re
from functools import partial
from itertools import permutations

from parsers.core.numbers import safe_float
from parsers.core.text_utils import fold_lookalikes, normalize_text, row_text
from parsers.quality import line_consistent

UNITS = {
    "шт", "шт.", "штук", "м", "м.", "мп", "м.п.", "пог.м", "м2", "м²", "м3", "кг", "г", "л", "уп", "уп.",
    "упак", "компл", "компл.", "комплект", "к-т", "пар", "пара", "рул", "рулон", "бухта", "ящ", "лист", "pcs",
}  # fmt: skip
STOP = re.compile(
    r"\b(разом|всього|усього|итого|всего|підсумок|итог|пдв|ндс|знижка|скидка|до сплати|к оплате|сума прописом)\b",
    re.IGNORECASE,
)
SKU_HEADER = re.compile(r"(арт|код|sku|article|модел)", re.IGNORECASE)
_QTY_UNIT = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*([a-zа-яіїє.²³]+)\s*$", re.IGNORECASE)
_BARCODE = re.compile(r"^\d{8,14}$")
_LETTERS = re.compile(r"[a-zа-яіїєґ]{3,}", re.IGNORECASE)


def _text(cell) -> str:
    if cell is None:
        return ""
    if isinstance(cell, float) and cell.is_integer():
        cell = int(cell)
    return normalize_text(cell)


def number(cell):
    """Число из ячейки; «12 шт» / «2,5 м» → 12 / 2.5."""
    if cell is None or isinstance(cell, bool):
        return None
    n = safe_float(cell)
    if n is not None:
        return n
    m = _QTY_UNIT.match(str(cell))
    if m and m.group(2).lower() in UNITS:
        return safe_float(m.group(1))
    return None


def _unit_in(cell) -> str:
    m = _QTY_UNIT.match(str(cell or ""))
    return m.group(2).lower() if m and m.group(2).lower() in UNITS else ""


def _is_item_like(row) -> bool:
    texts = [_text(c) for c in row]
    if STOP.search(" ".join(texts).lower()):
        return False
    has_name = any(_LETTERS.search(t) and len(t) >= 3 and number(t) is None for t in texts)
    numbers = sum(1 for c in row if (n := number(c)) is not None and n > 0)
    return has_name and numbers >= 2


HEADER_HINTS = {
    "qty": re.compile(r"(кільк|к-сть|кол-во|колич|к-во|qty|quantity)", re.IGNORECASE),
    "price": re.compile(r"(ціна|цена|price)", re.IGNORECASE),
    "total": re.compile(r"(сума|сумма|всього|итого|total|вартість|стоимость)", re.IGNORECASE),
}


# Есть и «без ПДВ», и «з ПДВ» — берём с ПДВ: это фактически уплаченная сумма (себестоимость для ФОП без ПДВ)
WITH_VAT = re.compile(r"\b(з|с|із|включ\S*)\s*(пдв|ндс)|with vat|brutto", re.IGNORECASE)
WITHOUT_VAT = re.compile(r"без\s*(пдв|ндс)|netto|without vat", re.IGNORECASE)


def _is_sequence(values) -> bool:
    """Номер позиции: 1, 2, 3… подряд (не может быть количеством)."""
    nums = [v for v in values if v is not None]
    if len(nums) < 2 or len(nums) != len(values) or any(v != int(v) for v in nums):
        return False
    return [int(v) for v in nums] == list(range(int(nums[0]), int(nums[0]) + len(nums)))


def _best_triple(rows, header=()):
    """
    (qty, price, total) — колонки с максимумом строк, где кол-во × цена = сумма.
    Ничьи (одинаковые значения в разных колонках) решают: подписи колонок, «номер позиции не количество»,
    сумма правее цены, соседство колонок.
    """
    width = max(len(r) for r in rows)
    values = {col: [number(r[col]) if col < len(r) else None for r in rows] for col in range(width)}
    numeric = [c for c, v in values.items() if sum(1 for x in v if x is not None and x > 0) >= max(1, len(rows) // 2)]

    def hint(col, kind):
        return bool(col < len(header) and HEADER_HINTS[kind].search(header[col] or ""))

    def vat(col):
        text = header[col] if col < len(header) else ""
        return 1 if WITH_VAT.search(text or "") else -1 if WITHOUT_VAT.search(text or "") else 0

    best, best_key = None, None
    for q, p, t in permutations(numeric, 3):
        hits = sum(1 for i in range(len(rows)) if line_consistent(values[q][i], values[p][i], values[t][i]))
        if not hits:
            continue
        key = (
            hits,
            hint(q, "qty") + hint(p, "price") + hint(t, "total"),
            not _is_sequence(values[q]),
            vat(p) + vat(t),
            t > p,
            -abs(t - p),
            q < p,
            -abs(p - q),
            t,
        )
        if best_key is None or key > best_key:
            best, best_key = (q, p, t), key
    return best, (best_key[0] if best_key else 0)


def _header_row(rows, first_item_idx):
    for idx in range(first_item_idx - 1, max(-1, first_item_idx - 4), -1):
        texts = [_text(c) for c in rows[idx]]
        if sum(1 for t in texts if _LETTERS.search(t)) >= 2:
            return idx
    return None


def detect_columns(rows: list) -> dict | None:
    """→ {"columns": {"name": i, "qty": i, "price": i, "total": i, "unit"?, "sku"?, "barcode"?}, "header_row", "first_row"}"""
    item_idx = [i for i, r in enumerate(rows) if r and _is_item_like(r)]
    if not item_idx:
        return None
    sample = [rows[i] for i in item_idx]
    header_idx = _header_row(rows, item_idx[0])
    header = [fold_lookalikes(_text(c)) for c in rows[header_idx]] if header_idx is not None else []
    triple, hits = _best_triple(sample, header)
    if not triple:
        return None
    q, p, t = triple
    data = [
        rows[i]
        for i in item_idx
        if line_consistent(*(number(rows[i][c]) if c < len(rows[i]) else None for c in triple))
    ]
    width = max(len(r) for r in data)
    used = {q, p, t}

    def column_values(col):
        return [_text(r[col]) if col < len(r) else "" for r in data]

    def share(col, predicate):
        values = column_values(col)
        return sum(1 for v in values if v and predicate(v)) / len(values)

    # название — самый длинный «буквенный» текст
    name_col, name_len = None, 0
    for col in range(width):
        if col in used:
            continue
        values = [v for v in column_values(col) if _LETTERS.search(v) and number(v) is None]
        if len(values) >= len(data) * 0.6:
            avg = sum(len(v) for v in values) / len(values)
            if avg > name_len:
                name_col, name_len = col, avg
    if name_col is None:
        return None
    used.add(name_col)
    columns = {"name": name_col, "qty": q, "price": p, "total": t}

    for col in range(width):
        if col not in used and share(col, lambda v: v.lower() in UNITS) >= 0.6:
            columns["unit"] = col
            used.add(col)
            break
    for col in range(width):
        if col not in used and share(col, lambda v: bool(_BARCODE.match(v.replace(" ", "")))) >= 0.6:
            columns["barcode"] = col
            used.add(col)
            break

    def is_position(col):
        return _is_sequence([number(v) for v in column_values(col)])

    sku_candidates = []
    for col in range(width):
        if col in used or is_position(col):
            continue
        values = [v for v in column_values(col) if v]
        if len(values) < len(data) * 0.6:
            continue
        code_like = sum(1 for v in values if len(v) <= 40 and len(v.split()) <= 3 and re.search(r"\d", v))
        if code_like >= len(values) * 0.6:
            by_header = bool(col < len(header) and SKU_HEADER.search(header[col] or ""))
            sku_candidates.append((by_header, -abs(col - name_col), col))
    if sku_candidates:
        columns["sku"] = max(sku_candidates)[2]

    return {
        "columns": columns,
        "header_row": header_idx,
        "first_row": item_idx[0],
        "consistent_rows": hits,
        "headers": {k: (header[v] if v < len(header) else "") for k, v in columns.items()},
    }


def _cell(row, columns, key):
    col = columns.get(key)
    return row[col] if col is not None and col < len(row) else None


def extract_items(rows: list, columns: dict, start: int = 0) -> list:
    """Строки товаров по заданным колонкам (определённым автоматически или вручную)."""
    items = []
    for row in rows[start:]:
        if not row:
            continue
        cell = partial(_cell, row, columns)
        name = _text(cell("name"))
        qty, price, total = number(cell("qty")), number(cell("price")), number(cell("total"))
        if STOP.search(row_text(row).lower()) and not (name and qty and price):
            if items:
                break
            continue
        if not name or not _LETTERS.search(name) or not (qty and price):
            continue
        unit = _text(cell("unit")).lower() if "unit" in columns else _unit_in(cell("qty"))
        barcode = re.sub(r"\D", "", _text(cell("barcode"))) if "barcode" in columns else ""
        items.append(
            {
                "position": len(items) + 1,
                "sku": _text(cell("sku")) if "sku" in columns else "",
                "barcode": barcode,
                "name": name,
                "qty": qty,
                "unit": unit,
                "price": price,
                "total": total if total else round(qty * price, 2),
            }
        )
    return items


def parse_table(rows: list) -> dict | None:
    found = detect_columns(rows)
    if not found:
        return None
    start = (found["header_row"] + 1) if found["header_row"] is not None else found["first_row"]
    return {**found, "items": extract_items(rows, found["columns"], start)}
