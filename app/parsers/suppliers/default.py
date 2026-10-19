# parsers/suppliers/default.py


import re

from parsers.core.date_utils import extract_date
from parsers.core.numbers import extract_numbers
from parsers.core.table_engine import TableEngine
from parsers.core.text_utils import fold_lookalikes, normalize_text, row_text

from ..base import BaseInvoiceParser


class DefaultParser(BaseInvoiceParser):
    supplier_code = "default"

    def detect_context(self, text: str) -> str:
        t = text.lower()

        supplier_keys = ["виконавець", "поставщик", "фоп", "продавец", "постачальник"]

        buyer_keys = ["отримувач", "покупатель", "клиент", "замовник", "клієнт", "получатель"]

        delivery_keys = ["адреса доставки", "адрес доставки", "доставка"]

        def match(keys):
            return any(k in t for k in keys)

        if match(supplier_keys):
            return "supplier"

        if match(buyer_keys):
            return "buyer"

        if match(delivery_keys):
            return "delivery"

        return "unknown"

    def extract_header(self, rows, context):

        supplier_phones = set()
        buyer_phones = set()

        supplier_emails = set()
        buyer_emails = set()

        supplier_text = []
        buyer_text = []
        delivery_lines = []

        for _i, row in enumerate(rows[:25]):
            text = row_text(row)
            if not text:
                continue

            ctx = self.detect_context(text)

            phones = re.findall(r"\+?\d[\d\s\-\(\)]{8,}", text)
            emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

            # =========================
            # SUPPLIER
            # =========================
            if ctx == "supplier":
                supplier_phones.update(p.strip() for p in phones)
                supplier_emails.update(emails)
                supplier_text.append(text)

            # =========================
            # BUYER
            # =========================
            elif ctx == "buyer":
                buyer_phones.update(p.strip() for p in phones)
                buyer_emails.update(emails)

                raw = text

                if ":" in raw:
                    raw = raw.split(":", 1)[1].strip()

                # НЕ фильтруем clean_entity — это ломает buyer
                if len(raw) > 3:
                    buyer_text.append(raw)

            # =========================
            # DELIVERY
            # =========================
            elif ctx == "delivery":
                delivery_lines.append(text)

        return {
            "supplier_text": normalize_text(" ".join(supplier_text)) or None,
            "buyer_text": normalize_text(" ".join(buyer_text)) or None,
            "supplier_phones": list(supplier_phones) or None,
            "buyer_phones": list(buyer_phones) or None,
            "supplier_emails": list(supplier_emails) or None,
            "buyer_emails": list(buyer_emails) or None,
            "delivery_address": normalize_text(" ".join(delivery_lines)) or None,
        }

    def extract_meta(self, rows, context):

        meta = {}

        header = self.extract_header(rows, context)
        full_text = " ".join(row_text(r) for r in rows)

        # =========================
        # NUMBER
        # =========================
        m = re.search(r"№\s*([^\s]+)", full_text)
        meta["number"] = m.group(1) if m else None

        meta["date"] = extract_date(full_text)
        # fallback
        if not meta["date"]:
            for row in rows[:15]:
                meta["date"] = extract_date(row_text(row))
                if meta["date"]:
                    break

        # =========================
        # HEADER DATA
        # =========================
        meta["supplier"] = header.get("supplier_text")
        meta["buyer"] = header.get("buyer_text")

        meta["supplier_phones"] = header.get("supplier_phones")
        meta["buyer_phones"] = header.get("buyer_phones")

        meta["supplier_emails"] = header.get("supplier_emails")
        meta["buyer_emails"] = header.get("buyer_emails")

        meta["delivery_address"] = header.get("delivery_address")

        # =========================
        # SHIPPING TERMS
        # =========================
        shipping = None

        for row in rows:
            text = row_text(row)
            lower = text.lower()

            if "отправка" in lower or "відправка" in lower:
                if ":" in text:
                    shipping = text.split(":", 1)[1].strip()
                else:
                    shipping = text
                break

        meta["shipping_terms"] = normalize_text(shipping) if shipping else None

        return meta

    def extract_items(self, rows, context):

        context.column_map = self.find_column_map(rows) or {}

        engine = TableEngine(rows, context)
        result = engine.run() or {}

        items = result.get("items") or []

        return items

    def extract_totals(self, rows, context):
        totals = {}

        for row in rows:
            text = row_text(row)
            lower = text.lower()
            nums = extract_numbers(row)

            if not nums:
                continue

            is_total = any(k in lower for k in ["итого", "разом", "всього"])
            is_vat = any(k in lower for k in ["ндс", "пдв", "vat"])
            is_weight = "вага" in lower
            is_volume = ("м3" in lower) or ("об" in lower)
            is_summary = "грн" in lower and "всего" in lower

            if is_total:
                totals["total"] = nums[-1]

            if is_vat:
                totals["vat"] = nums[-1]

            if is_weight and len(nums) > 0:
                totals["weight"] = nums[0]

            if is_volume and len(nums) > 0:
                totals["volume"] = nums[0]

            if is_summary:
                totals["summary"] = normalize_text(text)

        return totals

    def extract_footer(self, rows, context):
        footer = []

        for row in rows:
            text = row_text(row)
            lower = text.lower()

            if any(k in lower for k in ["грив", "коп", "всего на сумму", "разом"]):
                cleaned = text.strip()
                if len(cleaned) > 5:
                    footer.append(cleaned)

        return footer if footer else None

    def extract_warnings(self, rows, context):
        warnings = []

        for row in rows:
            text = row_text(row)
            lower = text.lower()

            if any(k in lower for k in ["внимание", "претензии", "важно", "не принимаются"]):
                cleaned = text.strip()
                if len(cleaned) > 5:
                    warnings.append(cleaned)

        return warnings if warnings else None

    def extract_signatures(self, rows, context):
        executor = None
        receiver = None

        for row in rows:
            text = row_text(row)
            lower = text.lower()

            if executor is None and any(k in lower for k in ["здав", "виконавець"]):
                executor = text.strip()

            if receiver is None and any(k in lower for k in ["прийняв", "получил"]):
                receiver = text.strip()

        return {"executor": executor, "receiver": receiver}

    def find_column_map(self, rows):
        for row in rows:
            normalized = [fold_lookalikes(str(v)) for v in row]
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
