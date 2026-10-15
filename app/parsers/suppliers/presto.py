import logging
import re

from parsers.core.date_utils import extract_date
from parsers.core.numbers import extract_numbers
from parsers.core.sku import extract_sku_from_row
from parsers.core.table_engine import TableEngine
from parsers.core.text_utils import normalize_text, row_text

from ..base import BaseInvoiceParser

logger = logging.getLogger(__name__)


class PrestoPSParser(BaseInvoiceParser):
    supplier_code = "presto_ps"

    def _extract_supplier_name(self, rows):
        """
        Берём только строку после 'Постачальник'
        и чистим мусор
        """

        for i, row in enumerate(rows[:15]):
            text = row_text(row)
            lower = text.lower()

            if "постачальник" in lower or "поставщик" in lower:
                # пробуем взять текущее значение
                parts = [p.strip() for p in row if p and str(p).strip()]

                # убираем ключевое слово
                parts = [p for p in parts if "постачальник" not in p.lower()]

                candidate = " ".join(parts).strip()

                # fallback: следующая строка (часто там имя)
                if not candidate and i + 1 < len(rows):
                    candidate = row_text(rows[i + 1]).strip()

                # финальная очистка
                candidate = re.sub(r"(№|код|адреса|рахунок).*", "", candidate, flags=re.I)
                candidate = re.sub(r"\s+", " ", candidate).strip()

                return candidate or None

        return None

    def extract_items_fallback(self, rows, cotext):
        engine = TableEngine(rows, cotext)
        result = engine.run()

        items = []

        # =========================
        # CASE 1: engine partially works
        # =========================
        if isinstance(result, dict) and result.get("items"):
            for i, item in enumerate(result["items"], start=1):
                # normalize engine output (safe guard)
                items.append(
                    {
                        "position": item.get("position", i),
                        "sku": item.get("sku") or "",
                        "name": item.get("name") or "",
                        "qty": item.get("qty"),
                        "unit": item.get("unit") or "шт",
                        "price": item.get("price"),
                        "total": item.get("total"),
                    }
                )

            self.totals_from_engine = result.get("totals", {})
            return items

        # =========================
        # CASE 2: engine failed → minimal safe fallback
        # (NO business logic duplication)
        # =========================
        position = 0

        for row in rows:
            text = row_text(row)
            lower = text.lower()

            # header detection (minimal)
            if any(k in lower for k in ["товар", "наименование", "назва"]):
                continue

            if any(k in lower for k in ["разом", "всього", "итого"]):
                break

            nums = extract_numbers(row)
            if len(nums) < 2:
                continue

            price = nums[-2]
            total = nums[-1]

            if total <= 0:
                continue

            position += 1

            sku = extract_sku_from_row(row)
            name = normalize_text(text)

            if sku:
                name = re.sub(rf"№\s*{re.escape(str(sku))}", "", name, flags=re.IGNORECASE)
                name = re.sub(rf"\b{re.escape(str(sku))}\b", "", name)

            items.append(
                {
                    "position": position,
                    "sku": sku or "",
                    "name": name.strip(),
                    "qty": None,  # IMPORTANT: engine owns qty logic
                    "unit": "шт",
                    "price": price,
                    "total": total,
                }
            )

        self.totals_from_engine = {}
        return items

    def detect_context(self, text: str):
        t = text.lower()

        # =========================
        # DELIVERY (highest priority)
        # =========================
        if any(x in t for x in ["адреса доставки", "адрес доставки", "доставка", "відвантаження", "shipping"]):
            return "delivery"

        # =========================
        # SUPPLIER
        # =========================
        if any(x in t for x in ["виконавець", "поставщик", "постачальник", "фоп", "тов", "ооо"]):
            return "supplier"

        # =========================
        # BUYER
        # =========================
        if any(x in t for x in ["замовник", "покупатель", "покупець", "customer", "client"]):
            return "buyer"

        return "unknown"

    def extract_header(self, rows, context):
        supplier_phones = []
        buyer_phones = []

        supplier_emails = []
        buyer_emails = []

        supplier_text = []
        buyer_text = []

        delivery_lines = []
        capture_delivery = False
        current_ctx = None

        for row in rows[:25]:
            text = row_text(row)

            lower = text.lower()

            if any(
                x in lower
                for x in [
                    "№ товар",
                    "кількість",
                    "ціна",
                    "сума",
                ]
            ):
                current_ctx = None
            if not text:
                continue

            ctx = self.detect_context(text)

            if ctx != "unknown":
                current_ctx = ctx
            else:
                ctx = current_ctx

            phones = re.findall(r"(?:\+38)?\s*\(?0\d{2}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}", text)
            emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

            # =========================
            # DELIVERY (improved capture)
            # =========================
            if ctx == "delivery":
                capture_delivery = True

            if capture_delivery:
                # stop conditions
                if any(x in text.lower() for x in ["товар", "разом", "всього", "итого", "сума"]):
                    capture_delivery = False
                else:
                    delivery_lines.append(text)

            # =========================
            # SUPPLIER
            # =========================
            if ctx == "supplier":
                supplier_phones.extend(phones)
                supplier_emails.extend(emails)
                supplier_text.append(text)

            # =========================
            # BUYER
            # =========================
            elif ctx == "buyer":
                buyer_phones.extend(phones)
                buyer_emails.extend(emails)
                buyer_text.append(text)

        return {
            "supplier_text": normalize_text(" ".join(dict.fromkeys(supplier_text))) or None,
            "buyer_text": normalize_text(" ".join(dict.fromkeys(buyer_text))) or None,
            "supplier_phones": list(set(supplier_phones)) or None,
            "buyer_phones": list(set(buyer_phones)) or None,
            "supplier_emails": list(set(supplier_emails)) or None,
            "buyer_emails": list(set(buyer_emails)) or None,
            "delivery_address": normalize_text(" ".join(delivery_lines)) or None,
        }

    # =========================
    # META
    # =========================
    def extract_meta(self, rows, context):
        meta = {}
        header = self.extract_header(rows, context) or {}

        full_text = " ".join(row_text(r) for r in rows if r)

        # =========================
        # NUMBER
        # =========================

        m = re.search(r"(?:№|N|No)\s*([A-Za-z0-9\/\-_]+)", full_text, re.IGNORECASE)
        meta["number"] = m.group(1) if m else None

        # =========================
        # DATE (FIXED - single source of truth)
        # =========================
        meta["date"] = extract_date(full_text)

        # =========================
        # HEADER SAFE ACCESS
        # =========================
        # meta["supplier"] = header.get("supplier_text")
        meta["supplier"] = self._extract_supplier_name(rows)
        meta["buyer"] = header.get("buyer_text")

        meta["supplier_phones"] = header.get("supplier_phones")
        meta["buyer_phones"] = header.get("buyer_phones")

        meta["supplier_emails"] = header.get("supplier_emails")
        meta["buyer_emails"] = header.get("buyer_emails")

        # =========================
        # IBAN
        # =========================
        iban = re.search(r"\bUA\s*\d{2}\s*\d{6}\s*\d{19}\b|\bUA\d{27}\b", full_text, re.I)
        meta["iban"] = iban.group(0).replace(" ", "") if iban else None

        # =========================
        # MFO
        # =========================
        mfo = re.search(r"МФО\s*[:\-]?\s*(\d{5,6})", full_text, re.I)
        meta["mfo"] = mfo.group(1) if mfo else None

        # =========================
        # EDRPOU
        # =========================

        edrpou = re.search(r"(?:ЄДРПОУ|ЕГРПОУ|код)\s*[:\-]?\s*(\d{8,10})", full_text, re.I)

        meta["supplier_edrpou"] = edrpou.group(1) if edrpou else None

        # =========================
        # BANK
        # =========================

        meta["bank_name"] = None

        bank_match = re.search(
            r'\b(АТ\s+КБ|АТ|ПАТ|АТ\s+аб|АТ\s+банк)\s+["\'«]?[А-ЯА-ЗЙ-ЯҐЄІЇa-zA-Z0-9_\-\s]{3,35}["\'»]?', full_text, re.I
        )

        if bank_match:
            bank_candidate = bank_match.group(0).strip()
            # Проверяем, что это реальное название банка, а не кусок слова типа "стабілізатор"
            if any(
                k in bank_candidate.lower() for k in ["банк", "приват", "раффайзен", "укрсиб", "ощад", "пумб", "моно"]
            ):
                # Отсекаем мусор, если он приклеился в конец регулярки
                bank_candidate = re.split(r"(?i)(від|мфо|курс|код|тел)", bank_candidate)[0]
                meta["bank_name"] = normalize_text(bank_candidate).strip()

        # meta["bank_name"] = (
        #     normalize_text(bank.group(0))
        #     if bank else None
        # )

        # =========================
        # DELIVERY ADDRESS
        # =========================
        delivery_address = []
        capture = False

        for row in rows:
            text = row_text(row)
            lower = text.lower().strip()

            if "адрес доставки" in lower or "адреса доставки" in lower:
                capture = True

                if ":" in text:
                    after = text.split(":", 1)[1].strip()
                    if 5 < len(after) < 120:
                        delivery_address.append(after)

                continue

            if capture:
                if any(
                    x in lower for x in ["товар", "разом", "всього", "итого", "менеджер", "сума", "грн", "шт", "вага"]
                ):
                    break

                if any(
                    x in lower for x in ["ул", "вул", "відділення", "отделение", "nova poshta", "нова пошта"]
                ) or re.search(r"\d{1,4}\s*[а-яА-Яa-zA-Z]", text):
                    if 5 < len(text.strip()) < 120:
                        delivery_address.append(text.strip())

        meta["delivery_address"] = normalize_text(" ".join(delivery_address)) if delivery_address else None

        meta["shipping_terms"] = (
            self._extract_shipping_terms(rows) if hasattr(self, "_extract_shipping_terms") else None
        )

        return meta

    def _extract_shipping_terms(self, rows):
        for row in rows:
            text = row_text(row)
            if not text:
                continue

            lower = text.lower()

            if any(x in lower for x in ["відправка", "отправка", "термін"]):
                # stop if it looks like table/footer
                if any(x in lower for x in ["товар", "разом", "всього", "итого"]):
                    return None

                value = text.split(":", 1)[1] if ":" in text else text
                value = value.strip()

                if 3 < len(value) < 120:
                    return normalize_text(value)

        return None

    def find_column_map(self, rows):
        for row in rows:
            normalized = [normalize_text(str(v).strip().lower()) for v in row]
            joined = " ".join(normalized)

            # stricter header detection
            if not (
                any(k in joined for k in ["кількість", "количество"])
                and any(k in joined for k in ["ціна", "цена"])
                and any(k in joined for k in ["сума", "сумма"])
            ):
                continue

            col_map = {}

            for i, v in enumerate(normalized):
                if "кількість" in v or "количество" in v:
                    col_map["qty"] = i

                elif "ціна" in v or "цена" in v:
                    col_map["price"] = i

                elif "сума" in v or "сумма" in v:
                    col_map["total"] = i

                elif any(x in v for x in ["товар", "наименование", "назва"]):
                    col_map["name"] = i

                elif any(x in v for x in ["од", "одиниця", "ед"]):
                    col_map["unit"] = i

            # =========================
            # VALIDATION (IMPORTANT FIX)
            # =========================
            if {"qty", "price", "total"}.issubset(col_map):
                return col_map

        return None

    # =========================
    # ITEMS (FIXED CORE)
    # =========================

    def extract_items(self, rows, context):
        context = getattr(self, "context", None)

        required_keys = ("header_index", "column_map")

        if not hasattr(context, "column_map"):
            raise ValueError("Parser context is required for TableEngine")

        if not all(k in context for k in required_keys):
            raise ValueError(f"Invalid context for TableEngine: missing {required_keys}")

        engine = TableEngine(rows, context)
        result = engine.run() or {}

        items = result.get("items") or []
        engine_totals = result.get("totals") or {}

        def safe_float(v):
            if v is None:
                return None
            try:
                if isinstance(v, str):
                    v = v.replace(" ", "").replace(",", ".")
                return float(v)
            except (ValueError, TypeError):
                return None

        valid_items = []

        for i in items:
            price = safe_float(i.get("price"))
            total = safe_float(i.get("total"))

            if price is None or total is None:
                continue

            if price <= 0 or total <= 0:
                continue

            i["price"] = price
            i["total"] = total
            valid_items.append(i)

        # =========================
        # DECISION
        # =========================
        if valid_items:
            self.totals_from_engine = engine_totals
            items = valid_items
        else:
            self.totals_from_engine = {}
            items = self.extract_items_fallback(rows)

        logger.debug("Presto: извлечено строк %s", len(items))
        return items

    # =========================
    # SIGNATURES (FIXED)
    # =========================

    def extract_signatures(self, rows, context):
        executor = []
        receiver = []

        for r in rows:
            t = row_text(r)
            lower = t.lower()

            if "виконавець" in lower or "исполнитель" in lower:
                executor.append(t)

            # FIX: receiver only role-based
            if "менеджер" in lower or "отримав" in lower or "получил" in lower:
                receiver.append(t)

        return {"executor": " | ".join(executor) or None, "receiver": " | ".join(receiver) or None}

    def extract_totals(self, rows, context):
        totals = {
            "total": None,
            "vat": None,
            "weight": None,
            "volume": None,
            "summary": None,
        }

        for row in rows:
            text = row_text(row)
            lower = text.lower()
            nums = extract_numbers(row)

            if not nums:
                continue

            # =========================
            # TOTAL
            # =========================
            if any(k in lower for k in ["разом", "всього", "итого", "total"]):
                totals["total"] = nums[-1]

            # =========================
            # WEIGHT
            # =========================
            if "вага" in lower:
                totals["weight"] = nums[0]

            # =========================
            # VOLUME
            # =========================
            if any(k in lower for k in ["м3", "м³", "об'єм", "объем"]):
                totals["volume"] = nums[0]

            # =========================
            # SUMMARY
            # =========================
            if totals["summary"] is None and any(k in lower for k in ["всього", "итого", "разом"]):
                totals["summary"] = text.strip()

        return totals

    def clean_name(self, text):
        if not text:
            return None

        # normalize spaces first
        text = str(text)

        # remove obvious SKU/ID markers
        text = re.sub(r"\b№\s*\d+\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bsku\b\s*[:\-]?\s*\d+", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\bарт(икул)?\b\s*[:\-]?\s*\d+", "", text, flags=re.IGNORECASE)

        # remove duplicated spaces
        text = re.sub(r"\s+", " ", text).strip()

        return text or None

    def parse(self, rows, context):
        engine = TableEngine(rows, context)
        engine_result = engine.run() or {}

        items = engine_result.get("items") or []
        totals = engine_result.get("totals") or {}

        buyer = engine_result.get("buyer")
        buyer_edrpou = engine_result.get("buyer_edrpou")
        buyer_raw = engine_result.get("buyer_raw")

        # =========================
        # FALLBACK FOR TOTALS
        # =========================
        if not totals.get("total"):
            totals = self._improved_extract_totals(rows)

        # =========================
        # META
        # =========================
        meta = self.extract_meta(rows, context) or {}

        meta.update(
            {
                "buyer": buyer or meta.get("buyer"),
                "buyer_edrpou": buyer_edrpou,
                "buyer_raw": buyer_raw,
            }
        )

        return {
            "items": items,
            "totals": totals,
            "meta": meta,
            "signatures": self.extract_signatures(rows, context),
            "supplier_code": self.supplier_code,
        }

    def _improved_extract_totals(self, rows):
        """Improved safe totals extraction"""

        keywords = ["усього", "всього", "сума", "разом", "итого", "total"]

        for row in rows[-15:]:
            text = row_text(row)
            lower = text.lower()

            if not any(word in lower for word in keywords):
                continue

            nums = extract_numbers(row)
            if not nums:
                continue

            # =========================
            # SAFE SELECTION (NOT max)
            # =========================
            # берем последний валидный number как более вероятный total
            total = None

            for n in reversed(nums):
                if n > 0:
                    total = n
                    break

            if total is None:
                continue

            return {"total": total, "summary": text.strip()}

        return {"total": None, "vat": None, "weight": None, "volume": None, "summary": None}
