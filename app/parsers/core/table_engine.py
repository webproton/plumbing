# parsers/core/table_engine.py
import logging
import re

from parsers.core.numbers import extract_numbers, safe_float
from parsers.core.sku import extract_sku_from_row
from parsers.core.text_utils import fold_lookalikes, normalize_text, row_text

logger = logging.getLogger(__name__)

HEADER_KEYWORDS = {
    "qty": [
        "кількість",
        "количество",
        "qty",
        "к-сть",
        "кільк",
        "кол-во",
        "кол",
        "кіл",
        "шт",
        "шт.",
        "к-во",
        "колич",
        "quantity",
        "кiлькiсть",
    ],
    "price": ["ціна", "цена", "price", "ціни", "ед.цена", "цена ед"],
    "total": ["сума", "сумма", "total", "всього", "итого", "сум"],
    "name": ["товар", "наименование", "назва", "опис", "найменування"],
    "unit": ["од", "одиниця", "ед", "unit", "од.вим", "од.изм"],
    # «№» / «номер» — это номер позиции, а не артикул (иначе позиция 1, 2, 3 попадала в SKU)
    "sku": ["арт", "код", "артикул", "sku", "article"],
    "barcode": ["штрих", "barcode", "ean", "штрихкод", "штрих-код", "ean13"],
    "position": ["№", "n", "#", "п/п", "поз"],
}

# Приоритет колонок (очень важно!)
COLUMN_PRIORITY = ["qty", "price", "total", "unit", "sku", "name"]

STOP_WORDS = ["разом", "итого", "всього", "підсумок", "грн", "ндс", "пдв"]


class TableEngine:
    def __init__(self, rows, context):
        self.rows = rows
        self.context = context
        self.state = "SEARCH_HEADER"
        self.position = 0

    def _cell(self, row, key):
        idx = self.context.column_map.get(key)
        if idx is None or idx < 0 or idx >= len(row):
            return None
        value = row[idx]
        if value is None:
            return None
        text = re.sub(r"\s+", " ", str(value)).strip()
        return text or None

    def is_valid_item_row(self, row, nums):
        text = row_text(row).lower()

        # 1. слишком короткая строка
        if len(text) < 5:
            return False

        # 2. стоп слова
        if any(w in text for w in STOP_WORDS):
            return False

        # 3. мусорные строки
        if any(
            x in text for x in ["сума прописом", "директор", "бухгалтер", "увага", "рахунок дійсний", "працюєм без пдв"]
        ):
            return False

        # должен быть текст товара
        text_parts = [x for x in re.split(r"\s+", text) if not re.fullmatch(r"[\d.,/]+", x)]

        if len(text_parts) < 2:
            return False

        # 4. должно быть минимум 2 числа
        if len(nums) < 2:
            return False

        price, total = self._smart_extract_price_total(row)

        if price is None or total is None:
            return False

        # 5. цена и сумма должны быть > 0
        if price <= 0 or total <= 0:
            return False

        # 6. сумма не меньше цены — кроме дробного количества (0.5 м трубы: сумма < цены)
        if total < price and abs(total - price) > 0.01:
            qty = safe_float(self._cell(row, "qty"))
            if not (qty and 0 < qty < 1 and abs(qty * price - total) <= max(0.02, total * 0.01)):
                return False

        return True

    # =========================
    # STEP 1: FIND HEADER
    # =========================
    def find_header(self):
        for i, row in enumerate(self.rows):
            normalized = [normalize_text(str(v).strip().lower()) if v is not None else "" for v in row]
            if len(normalized) < 3:
                continue

            found = {}
            for key, variants in HEADER_KEYWORDS.items():
                for col_idx, cell in enumerate(row):
                    if col_idx in found.values():
                        continue  # колонка уже распознана под другое поле
                    cell_str = fold_lookalikes(str(cell)) if cell is not None else ""

                    tokens = re.split(r"[\s._\-]+", cell_str)

                    if any(v == t for v in variants for t in tokens):
                        # Дополнительная проверка — не путаем "кол" из "колір" и т.д.
                        if key == "qty" and re.search(r"колір|колон|колонк", cell_str):
                            continue
                        found[key] = col_idx
                        break
            # Если нашли хотя бы qty + (price или total) — почти наверняка заголовок
            if "qty" in found and ("price" in found or "total" in found):
                self.context.header_index = i
                if not self.context.column_map:
                    self.context.column_map = found
                else:
                    for k, v in found.items():
                        self.context.column_map.setdefault(k, v)

                self.state = "ITEMS"
                logger.debug("Заголовок таблицы: строка %s, колонки %s", i, found)
                return True

        return False

    # =========================
    # STEP 2: READ ROWS
    # =========================
    def extract_rows(self):

        if self.context.header_index is None:
            return []

        items = []
        self.position = 0

        for row in self.rows[self.context.header_index + 1 :]:
            text = row_text(row).lower()
            nums = extract_numbers(row)

            # =========================
            # STATE: ITEMS
            # =========================
            if self.state != "ITEMS":
                break

            # =========================
            # FOOTER DETECTION
            # =========================
            if any(k in text for k in ["итого", "разом", "всього"]):
                # footer почти всегда содержит суммы
                if len(nums) >= 1:
                    self.state = "FOOTER"
                    break

            # =========================
            # SKIP INVALID ROW
            # =========================

            if not self.is_valid_item_row(row, nums):
                continue

            self.position += 1

            item = self.parse_row(row, nums, self.position)

            if item:
                items.append(item)

        return items

    # =========================
    # STEP 3: PARSE ROW
    # =========================
    def parse_row(self, row, nums, position):

        def safe_get(idx):
            if idx is None:
                return None

            if idx < 0 or idx >= len(row):
                return None

            return row[idx]

        raw_text = row_text(row)

        # =========================
        # PRICE / TOTAL
        # =========================
        price, total = self.extract_price_total(row, safe_get)
        if price is None or total is None:
            return None

        # =========================
        # QTY (STRICT COLUMN FIRST)
        # =========================

        qty = self.extract_qty(row, raw_text, nums, position)

        # =========================
        # UNIT
        # =========================
        unit = self.extract_unit(row, safe_get)

        # =========================
        # SKU (SINGLE SOURCE OF TRUTH)
        # =========================

        # Колонки из заголовка надёжнее эвристик по всей строке
        sku = self._cell(row, "sku") or self.extract_sku(row, raw_text)
        barcode = self._cell(row, "barcode")
        name = self._cell(row, "name") or self.extract_name(row, raw_text, sku, nums, price, total, qty)

        return {
            "position": position,
            "sku": sku,
            "barcode": barcode,
            "name": name,
            "qty": qty,
            "unit": unit or "",
            "price": price,
            "total": total,
        }

    # =========================
    # TOTALS EXTRACTION
    # =========================
    def extract_totals(self):
        totals = {
            "total": None,
            "vat": None,
            "weight": None,
            "volume": None,
            "summary": None,
        }

        for row in self.rows:
            text = row_text(row).lower()

            # =========================
            # STRICT REGEX FIRST
            # =========================
            m = re.search(
                r"(усього|всього|итого|total)\s*[:\-]?\s*(\d+[.,]\d{2})",
                text,
                re.I,
            )

            if m:
                totals["total"] = safe_float(m.group(2))
                break

            # =========================
            # FALLBACK
            # =========================
            if any(k in text for k in ["усього", "всього", "итого", "total"]):
                numbers = [n for n in extract_numbers(row) if n > 0]

                if numbers:
                    # invoice total обычно последнее число
                    totals["total"] = numbers[-1]
                    break

        return totals

    # =========================
    # HELPERS
    # =========================

    def extract_price_total(self, row, safe_get):

        price = None
        total = None

        # =========================
        # HEADER MAPPING
        # =========================
        if "price" in self.context.column_map:
            price = safe_float(safe_get(self.context.column_map["price"]))

        if "total" in self.context.column_map:
            total = safe_float(safe_get(self.context.column_map["total"]))

        # =========================
        # FALLBACK
        # =========================
        if price is None or total is None or price <= 0 or total <= 0:
            price, total = self._smart_extract_price_total(row)

        # =========================
        # FINAL VALIDATION
        # =========================
        if price is None or total is None:
            return None, None

        return price, total

    def _smart_extract_price_total(self, row):

        raw_text = row_text(row).lower()

        # =========================
        # ALL POSITIVE NUMBERS
        # =========================
        nums = [n for n in extract_numbers(row) if n > 0]

        if len(nums) < 2:
            return None, None

        # =========================
        # MONEY VALUES PRIORITY
        # =========================
        decimal = re.findall(
            r"\d+[.,]\d{1,2}",
            raw_text,
        )

        decimal_nums = []

        for x in decimal:
            val = safe_float(x)

            if val is not None and val > 0:
                decimal_nums.append(val)

        candidates = decimal_nums if len(decimal_nums) >= 2 else nums

        if len(candidates) < 2:
            return None, None

        # =========================
        # SORT ASC
        # =========================
        candidates = sorted(candidates)

        # invoice heuristic:
        # total usually biggest
        total = candidates[-1]

        # price usually before total
        price = candidates[-2]

        # =========================
        # VALIDATION
        # =========================
        if price <= 0 or total <= 0:
            return None, None

        if total < price:
            return None, None

        return price, total

    def detect_unit(self, row):

        for v in row:
            v = str(v).lower().strip(".,() ")

            if v in ["шт", "кг", "л", "м", "уп", "ящ"]:
                return v

        return None

    def extract_unit(self, row, safe_get):

        unit_raw = safe_get(self.context.column_map.get("unit"))

        if unit_raw:
            return str(unit_raw).lower().strip(".,() ")

        return self.detect_unit(row)

    def extract_qty(self, row, raw_text, nums, position):

        # =========================
        # 1. COLUMN
        # =========================
        if "qty" in self.context.column_map:
            col_idx = self.context.column_map["qty"]

            if col_idx < len(row):
                qty = safe_float(row[col_idx])

                if qty and 0 < qty <= 10000:
                    return qty

        # =========================
        # 2. NUMBER + UNIT
        # =========================
        matches = re.findall(
            r"(\d{1,6})\s*(шт|уп|бухта|ящ|м|кг|л)",
            raw_text,
            re.IGNORECASE,
        )

        if matches:
            return float(matches[-1][0])

        # =========================
        # 3. FALLBACK
        # =========================
        if len(nums) < 3:
            return None

        price = nums[-2]
        total = nums[-1]

        if price <= 0 or total <= 0:
            return None

        candidates = [
            n
            for n in nums
            if n > 0 and n not in (price, total) and abs(n - position) > 0  # защита от позиции
        ]

        if not candidates:
            return None

        # qty usually first numeric before money
        return float(candidates[0])

    def extract_sku(self, row, raw_text):

        sku_engine = extract_sku_from_row(row)

        if not sku_engine:
            m = re.search(
                r"№\s*([^\s,;]+)",
                raw_text,
            )

            sku_engine = m.group(1) if m else None

        return sku_engine or ""

    def extract_name(self, row, raw_text, sku, nums, price, total, qty):

        # исходный текст строки
        name = raw_text.strip()

        # =========================
        # REMOVE POSITION NUMBER
        # "1 Кабель..." -> "Кабель..."
        # =========================
        name = re.sub(r"^\s*\d+\.?\s+", "", name)

        # =========================
        # NORMALIZE SKU
        # "5116" -> "№ 5116"
        # =========================
        if sku:
            if not re.search(rf"№\s*{re.escape(sku)}", name, re.I):
                name = re.sub(rf"\b{re.escape(sku)}\b", f"№ {sku}", name, flags=re.I)

        # =========================
        # REMOVE NUMERIC VALUES
        # qty / price / total
        # =========================
        def remove_value(text, val, protect_sku=None):
            if val is None:
                return text

            variants = [
                str(val),
                str(val).replace(".", ","),
                f"{val:g}",
            ]

            for v in variants:
                # защита SKU
                if protect_sku and v == str(protect_sku):
                    continue

                text = re.sub(rf"\b{re.escape(v)}\b", "", text)

            return text

        # удаляем qty
        name = remove_value(name, qty, sku)

        # удаляем price
        name = remove_value(name, price, sku)

        # удаляем total
        name = remove_value(name, total, sku)

        # =========================
        # REMOVE "QTY + UNIT"
        # "10 шт"
        # "5 кг"
        # =========================
        if qty:
            qty_patterns = [
                f"{qty:g}",
                str(qty).replace(".", ","),
            ]

            for q in qty_patterns:
                name = re.sub(rf"\b{re.escape(q)}\s*(шт|уп|бухта|ящ|м|кг|л)\b", "", name, flags=re.I)

        # =========================
        # CLEAN EXTRA SPACES
        # =========================
        name = re.sub(r"\s+", " ", name).strip()

        # remove trailing punctuation
        name = re.sub(r"[,.;]\s*$", "", name)

        return name

    def extract_buyer(self):
        """Улучшенный парсинг Платника / Покупателя"""
        buyer_info = []
        capture = False

        buyer_start_keywords = [
            "платник",
            "замовник",
            "покупець",
            "покупатель",
            "отримувач",
            "получатель",
            "клієнт",
            "клиент",
            "контрагент",
        ]
        stop_keywords = [
            "виконавець",
            "поставщик",
            "разом",
            "всього",
            "сума",
            "итого",
            "товари",
            "найменування",
            "адреса доставки",
        ]

        for row in self.rows:
            text = row_text(row).strip()
            if not text:
                continue
            lower = text.lower()

            # === СТАРТ ЗАХВАТА ===
            if not capture and any(kw in lower for kw in buyer_start_keywords):
                capture = True

                # Если в этой же строке есть ":" — берём текст после него
                if ":" in text:
                    after = text.split(":", 1)[1].strip()
                    if after and len(after) > 3:
                        buyer_info.append(after)
                else:
                    # Если ":" нет — добавляем саму строку без слова "Платник"
                    cleaned = re.sub(
                        r"(платник|замовник|покупець|покупатель|отримувач|получатель|клієнт|клиент|контрагент)\s*[:\-]?",
                        "",
                        text,
                        flags=re.I,
                    ).strip()
                    if cleaned:
                        buyer_info.append(cleaned)
                continue

            # === ЗАХВАТ СТРОК ===
            if capture:
                # Проверка на остановку
                if any(stop in lower for stop in stop_keywords):
                    break

                # Пропускаем служебные строки
                if any(x in lower for x in ["директор", "бухгалтер", "рахунок дійсний", "підпис", "м.п."]):
                    continue

                if len(text) < 4:
                    continue

                buyer_info.append(text)

        buyer_raw = " ".join(buyer_info).strip()

        # Извлекаем ЕДРПОУ
        edrpou_match = re.search(r"(?:єдрпоу|едрпоу|код\s+по\s+єдрпоу|код)\s*[:\-]?\s*(\d{8,10})", buyer_raw, re.I)
        edrpou = edrpou_match.group(1) if edrpou_match else None

        # Финальная очистка
        buyer_clean = normalize_text(buyer_raw)

        return {"buyer": buyer_clean or None, "buyer_edrpou": edrpou, "buyer_raw": buyer_raw or None}

    # =========================
    # MAIN
    # =========================
    def run(self):

        # reset state
        self.state = "SEARCH_HEADER"
        self.position = 0

        # reset context
        self.context.header_index = None

        # НЕ ЗАТИРАТЬ supplier column_map
        if not self.context.column_map:
            self.context.column_map = {}

        # =========================
        # FIND HEADER + ITEMS
        # =========================
        if not self.find_header():
            items = []
        else:
            items = self.extract_rows()

        # =========================
        # TOTALS
        # =========================
        totals = self.extract_totals()

        # =========================
        # BUYER
        # =========================
        buyer_data = self.extract_buyer()

        # =========================
        # RESULT
        # =========================
        return {
            "items": items,
            "totals": totals,
            "buyer": buyer_data["buyer"],
            "buyer_edrpou": buyer_data["buyer_edrpou"],
            "buyer_raw": buyer_data["buyer_raw"],
        }
