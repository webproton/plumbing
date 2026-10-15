# parsers/suppliers/ber.py
from ..base import BaseInvoiceParser


class BerParser(BaseInvoiceParser):
    supplier_code = "ber"

    def extract_meta(self, rows):
        # Это клиент (покупатель), а не поставщик
        return {"supplier": "Балабановский рынок (клиент)", "buyer": "Балабанов ЧП балабановский р-к"}

    def extract_items(self, rows):
        # Простой парсер для документов клиента Балабанов
        items = []
        for row in rows:
            values = [v for v in row if v not in (None, "")]
            if len(values) < 3:
                continue
            try:
                price = float(str(values[-2]).replace(",", "."))
                total = float(str(values[-1]).replace(",", "."))
                name = " ".join(map(str, values[:-2]))
                items.append({"name": name, "price": price, "total": total})
            except (ValueError, TypeError):
                continue
        return items
