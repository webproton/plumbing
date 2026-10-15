# parsers/core/sku.py
import re

from .text_utils import normalize_text, row_text


# =========================
# SKU NORMALIZER
# =========================
def normalize_sku(sku):
    if not sku:
        return None

    sku = normalize_text(str(sku)).upper()

    # убираем мусорные пробелы
    sku = re.sub(r"\s+", " ", sku).strip()

    return sku


# =========================
# SKU PATTERNS (PRIORITY ORDER)
# =========================
SKU_PATTERNS = [
    # 1. № 5141 / №5141 / № ABC-123
    r"№\s*([A-Za-z0-9\-]{2,})",
    # 2. арт. 5141 / арт 5141
    r"арт\.?\s*([A-Za-z0-9\-]{2,})",
    # 3. sku 5141
    r"sku\.?\s*([A-Za-z0-9\-]{2,})",
    # 4. code 5141
    r"code\.?\s*([A-Za-z0-9\-]{2,})",
]


# =========================
# CORE EXTRACTOR
# =========================
def extract_sku_from_row(row):
    if not row:
        return None

    text = row_text(row)
    if not text:
        return None

    # =========================
    # 1. STRONG PATTERNS (№ / арт / sku)
    # =========================
    for pattern in SKU_PATTERNS:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            return normalize_sku(m.group(1))

    # =========================
    # 2. STRUCTURED SKU LIKE ABC-123 / AS-M69
    # =========================
    m = re.search(r"\b[A-Za-z]{1,6}-[A-Za-z0-9\-]{2,}\b", text)
    if m:
        return normalize_sku(m.group(0))

    # =========================
    # 3. ISOLATED SKU NUMBER (SAFE FILTER)
    # =========================
    # важно: НЕ ловим цены (защита)
    numbers = re.findall(r"\b\d{3,6}\b", text)

    if numbers:
        # фильтр: не брать если строка выглядит как цена/сумма
        if not re.search(r"\d+[.,]\d{2}", text):
            # if not re.search(r"\d+\.\d{2}", text):  # 1.269 / 253.80

            return normalize_sku(numbers[0])

    # =========================
    # 4. SPLIT ROW FALLBACK (SAFE VERSION)
    # =========================
    values = [str(v).strip() for v in row if v]

    for i in range(len(values) - 1):
        a = values[i]
        b = values[i + 1]

        # защита от quantity / price confusion
        if re.fullmatch(r"\d{1,2}", a) and re.fullmatch(r"\d{3,6}", b):
            # не брать если похоже на qty + price
            if float(b) < 100000:
                return normalize_sku(b)

    return None
