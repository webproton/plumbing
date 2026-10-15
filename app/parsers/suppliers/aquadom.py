# parsers/suppliers/aquadom.py
import re

from parsers.core.date_utils import extract_date
from parsers.core.numbers import extract_numbers
from parsers.core.table_engine import TableEngine
from parsers.core.text_utils import normalize_text, row_text

from ..base import BaseInvoiceParser


class AquadomParser(BaseInvoiceParser):
    supplier_code = "aquadom"

    # =========================
    # CONTACT ENGINE
    # =========================
    def extract_contact_and_phones(self, rows, context):
        from parsers.core.text_utils import normalize_text, row_text

        phones = []
        candidates = []

        for row in rows:
            text = row_text(row)
            if not text:
                continue

            lower = text.lower()

            # =========================
            # PHONES
            # =========================
            found_phones = re.findall(r"\+?\d[\d\s\-\(\)]{8,}", text)
            if found_phones:
                phones.extend(found_phones)

            # =========================
            # CLEAN CONTACT CANDIDATE LINE
            # =========================
            if found_phones or "тел" in lower:
                cleaned = text
                cleaned = re.sub(r"\d{9,12}", "", cleaned)
                cleaned = re.sub(r"тел\.?:?", "", cleaned, flags=re.IGNORECASE)
                cleaned = re.sub(r"адрес", "", cleaned, flags=re.IGNORECASE)

                cleaned = re.sub(r"\s+", " ", cleaned).strip()

                parts = re.split(r"[;,]", cleaned)

                for part in parts:
                    part = part.strip()

                    if not part:
                        continue

                    # =========================
                    # HARD FILTERS (ВАЖНО)
                    # =========================

                    # 1. слишком длинное = мусор
                    if len(part) > 60:
                        continue

                    # 2. есть цифры → не имя
                    if re.search(r"\d", part):
                        continue

                    # 3. стоп-слова (товары / инструкции)
                    if any(
                        x in part.lower()
                        for x in [
                            "керамик",
                            "товар",
                            "провер",
                            "внимание",
                            "шт",
                            "исполн",
                            "виконавець",
                            "получил",
                            "менеджер",
                        ]
                    ):
                        continue

                    # 4. должно быть похоже на имя/фамилию/организацию
                    # (минимум 2 слова или фамилия)
                    words = part.split()

                    if len(words) == 0:
                        continue
                    # стоп для организаций/служебных слов
                    if any(x in part.lower() for x in ["ооо", "чп", "тов", "склад", "цех"]):
                        continue
                    # =========================
                    # SCORE SYSTEM (ВАЖНО)
                    # =========================
                    score = 0

                    # похоже на фамилию
                    if len(words) == 1 and words[0][0].isupper():
                        score += 2

                    # содержит кириллицу (имя)
                    if re.search(r"[А-Яа-я]", part):
                        score += 2

                    # не содержит мусорных слов
                    if not any(x in part.lower() for x in ["р-к", "склад", "цех"]):
                        score += 1

                    if score >= 3:
                        candidates.append(part)

        # =========================
        # FINAL PICK
        # =========================
        contact_person = candidates[-1] if candidates else None

        return {
            "buyer_phones": list(set(phones)) if phones else None,
            "contact_person": normalize_text(contact_person) if contact_person else None,
        }

    def detect_context(self, text: str):
        t = text.lower()

        if any(x in t for x in ["виконавець", "поставщик", "фоп", "постачальник"]):
            return "supplier"

        if any(x in t for x in ["замовник", "покупатель", "клиент", "клієнт"]):
            return "buyer"

        if any(x in t for x in ["адреса доставки", "адрес доставки", "доставка"]):
            return "delivery"

        return "unknown"

    def extract_header(self, rows, context):

        supplier_phones = []
        buyer_phones = []

        supplier_emails = []
        buyer_emails = []

        supplier_text = []
        buyer_text = []

        for i, row in enumerate(rows[:25]):
            text = row_text(row)
            ctx = self.detect_context(text)

            phones = re.findall(r"\+?\d[\d\s\-\(\)]{8,}", text)
            emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

            # =========================
            # SUPPLIER
            # =========================
            if ctx == "supplier":
                supplier_phones += phones
                supplier_emails += emails
                supplier_text.append(text)

                # 🔥 ВАЖНО: смотрим следующую строку (часто телефоны там)
                if i + 1 < len(rows):
                    next_text = row_text(rows[i + 1])
                    next_phones = re.findall(r"\+?\d[\d\s\-\(\)]{8,}", next_text)
                    supplier_phones += next_phones

            # =========================
            # BUYER
            # =========================
            elif ctx == "buyer":
                buyer_phones += phones
                buyer_emails += emails
                buyer_text.append(text)

        # =========================
        # CLEAN
        # =========================
        supplier_phones = list(set(p.strip() for p in supplier_phones if len(p) > 8)) or None
        buyer_phones = list(set(p.strip() for p in buyer_phones if len(p) > 8)) or None

        supplier_emails = list(set(supplier_emails)) or None
        buyer_emails = list(set(buyer_emails)) or None

        return {
            "supplier_text": normalize_text(" ".join(supplier_text)) or None,
            "buyer_text": normalize_text(" ".join(buyer_text)) or None,
            "supplier_phones": supplier_phones,
            "buyer_phones": buyer_phones,
            "supplier_emails": supplier_emails,
            "buyer_emails": buyer_emails,
        }

    # =========================
    # META
    # =========================
    def extract_meta(self, rows, context):

        meta = {
            "raw_title": None,
            "number": None,
            "date": None,
            "shipping_terms": None,
            "contact_person": None,
            "buyer": None,
            "delivery_address": None,
            "buyer_phones": None,
            "supplier": None,
            "supplier_phones": None,
            "supplier_emails": None,
            "buyer_emails": None,
        }

        header = self.extract_header(rows, context)

        buyer = None
        address = None
        delivery = None

        supplier_phones = []
        supplier_emails = []

        contact_person = None

        # =========================
        # MAIN LOOP
        # =========================
        for i, row in enumerate(rows):
            text = row_text(row)
            if not text:
                continue

            lower = text.lower()

            # =========================
            # TITLE
            # =========================
            if "накладная" in lower:
                meta["raw_title"] = text

                m = re.search(r"№\s*([^\s]+)", text)
                if m:
                    meta["number"] = m.group(1)

                date = extract_date(text)
                if date:
                    meta["date"] = date

            # =========================
            # BUYER
            # =========================
            if "покупатель" in lower:
                parts = re.split(r"покупатель\s*:", text, flags=re.I)
                if len(parts) > 1:
                    buyer = parts[-1].strip()
                else:
                    buyer = text.split(":")[-1].strip()

                if i + 1 < len(rows):
                    next_text = row_text(rows[i + 1])
                    if next_text and "адрес" in next_text.lower():
                        address = re.split(r"адрес\s*:", next_text, flags=re.I)[-1].strip()

            # =========================
            # DELIVERY
            # =========================
            if "адрес доставки" in lower:
                delivery = re.split(r"адрес доставки\s*[:\-]?", text, flags=re.I)[-1].strip()

            # =========================
            # SHIPPING
            # =========================
            if "відправка" in lower or "отправка" in lower:
                meta["shipping_terms"] = text

            # =========================
            # SUPPLIER HEADER
            # =========================
            if any(x in lower for x in ["поставщик", "фоп", "тов", "ooo", "чп"]):
                supplier_phones += re.findall(r"\+?\d[\d\s\-\(\)]{8,}", text)
                supplier_emails += re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

            # =========================
            # FALLBACK PHONES
            # =========================
            if not supplier_phones:
                for r in rows[:15]:
                    t = row_text(r)
                    if not t:
                        continue

                    low = t.lower()

                    if any(x in low for x in ["покупатель", "замовник", "адрес"]):
                        continue

                    phones = re.findall(r"\+?\d[\d\s\-\(\)]{8,}", t)

                    if phones:
                        supplier_phones += phones

        # =========================
        # CONTACT ENGINE (ONCE)
        # =========================
        contact = self.extract_contact_and_phones(rows, context)

        # =========================
        # CONTACT PERSON
        # =========================
        if buyer:
            cleaned = re.sub(r"№.*", "", buyer)
            cleaned = re.sub(r"чп|ооо|фоп", "", cleaned, flags=re.I)
            cleaned = re.sub(r"р-к.*", "", cleaned, flags=re.I)
            cleaned = re.sub(r"\s+", " ", cleaned).strip()

            for p in cleaned.split():
                if len(p) > 2 and not re.search(r"\d", p):
                    contact_person = p
                    break

        # =========================
        # FINAL META
        # =========================
        meta["buyer"] = buyer
        meta["delivery_address"] = delivery or address
        meta["contact_person"] = contact_person

        meta["buyer_phones"] = contact.get("buyer_phones")

        meta["supplier"] = header.get("supplier_text")
        meta["supplier_phones"] = list(set(supplier_phones)) or None
        meta["supplier_emails"] = list(set(supplier_emails)) or None

        return meta

    # =========================
    # ITEMS
    # =========================
    def extract_items(self, rows, context):
        engine = TableEngine(rows, context)
        return engine.run().get("items", [])

    # =========================
    # TOTALS
    # =========================
    def extract_totals(self, rows, context):
        totals = {}

        for row in rows:
            values = [v for v in row if v not in (None, "")]
            if not values:
                continue

            text = row_text(row).lower()
            nums = extract_numbers(values)

            if any(x in text for x in ["итого", "разом"]):
                if nums:
                    totals["total"] = nums[-1]

            if "налога" in text or "податку" in text:
                totals["vat"] = nums[-1] if nums else 0.0

            if "всего" in text:
                totals["summary"] = normalize_text(row_text(row))

        return totals

    # =========================
    # FOOTER
    # =========================
    def extract_footer(self, rows, context):
        return [row_text(row) for row in rows if any(x in row_text(row).lower() for x in ["вага", "об", "грив"])]

    # =========================
    # WARNINGS
    # =========================
    def extract_warnings(self, rows, context):
        return [
            row_text(row)
            for row in rows
            if any(x in row_text(row).lower() for x in ["внимание", "претензии", "пожалуйста"])
        ]

    # =========================
    # SIGNATURES
    # =========================
    def extract_signatures(self, rows, context):
        executor = []
        receiver = []

        for row in rows:
            text = row_text(row).lower()

            if "виконавець" in text or "исполнител" in text:
                executor.append(row_text(row))

            if "менеджер" in text or "получил" in text:
                receiver.append(row_text(row))

        return {
            "executor": " | ".join(executor) or None,
            "receiver": " | ".join(receiver) or None,
        }
