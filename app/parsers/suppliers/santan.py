# parsers/suppliers/santan.py

from ..base import BaseInvoiceParser
from parsers.core.text_utils import row_text, normalize_text
from parsers.core.table_engine import TableEngine
from parsers.core.numbers import extract_numbers
import re

class SantanParser(BaseInvoiceParser):
    supplier_code = "santan"
    
    def detect_context(self, text: str):
            t = text.lower()
            # Если в шапке появились маркеры, распознаем их
            if any(x in t for x in ["виконавець", "поставщик", "постачальник", "фоп", "тов", "ooo", "фирма"]):
                return "supplier"
            if any(x in t for x in ["замовник", "покупатель", "платник", "покупець", "клієнт"]):
                return "buyer"
            return "unknown"
        
    def extract_header(self, rows, context):
            import re

            supplier_phones = []
            buyer_phones = []
            supplier_emails = []
            buyer_emails = []
            supplier_text = []
            buyer_text = []

            for i, row in enumerate(rows[:25]):
                text = row_text(row)
                if not text:
                    continue
                    
                ctx = self.detect_context(text)

                # Стандартный поиск телефонов и почты по регуляркам
                phones = re.findall(r"\+?\d[\d\s\-\(\)]{8,}", text)
                emails = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text)

                if ctx == "supplier":
                    supplier_phones += phones
                    supplier_emails += emails
                    supplier_text.append(text)
                    if i + 1 < len(rows):
                        next_text = row_text(rows[i + 1])
                        supplier_phones += re.findall(r"\+?\d[\d\s\-\(\)]{8,}", next_text)

                elif ctx == "buyer":
                    buyer_phones += phones
                    buyer_emails += emails
                    buyer_text.append(text)

            # Чистим дубликаты
            s_text = normalize_text(" ".join(supplier_text))
            b_text = normalize_text(" ".join(buyer_text))

            # 🔥 СТРАХОВКА: Если документ пришел без шапки, s_text будет пустым.
            # В таком случае принудительно пишем "SANTAN", чтобы в базе не было null.
            if not s_text:
                s_text = "SANTAN"

            return {
                "supplier_text": s_text,
                "buyer_text": b_text or None,
                "supplier_phones": list(set(p.strip() for p in supplier_phones if len(p) > 8)) or None,
                "buyer_phones": list(set(p.strip() for p in buyer_phones if len(p) > 8)) or None,
                "supplier_emails": list(set(supplier_emails)) or None,
                "buyer_emails": list(set(buyer_emails)) or None,
            }
            
    def extract_meta(self, rows, context):
            full_text = " ".join(row_text(r) for r in rows if r)
            header = self.extract_header(rows, context)
            
            meta = {
                "number": None,
                "date": None,
                "supplier": header.get("supplier_text"),
                "buyer": header.get("buyer_text"),
                "supplier_phones": header.get("supplier_phones"),
                "buyer_phones": header.get("buyer_phones"),
                "supplier_emails": header.get("supplier_emails"),
                "buyer_emails": header.get("buyer_emails"),
                "delivery_address": None,
                "shipping_terms": None,
                "iban": None,
                "mfo": None,
                "supplier_edrpou": None,
                "buyer_edrpou": None,
                "buyer_raw": header.get("buyer_text")
            }

            date_match = re.search(r'(\d{2})\.(\d{2})\.(\d{4})', full_text)
            if date_match:
                day, month, year = date_match.groups()
                meta["date"] = f"{year}-{month}-{day}"

            return meta

    # =========================
    # ИСПРАВЛЕННЫЙ ПОИСК КОЛОНОК
    # =========================
    def find_column_map(self, rows):
        """
        Сканирует первые строки. Находит двухстрочную шапку,
        сопоставляет индексы и фиксирует header_index на второй строке.
        """
        for idx, row in enumerate(rows[:20]):
            row_clean = [normalize_text(str(cell).strip().lower()) for cell in row]
            joined = " ".join(row_clean)

            if "номенклатура" in joined:
                # Нашли первую строку шапки. Заглядываем во вторую (где Цена и Од.)
                next_idx = idx + 1
                next_row = [normalize_text(str(c).strip().lower()) for c in rows[next_idx]] if next_idx < len(rows) else []

                col_map = {}

                # 1. Сначала ищем по первой строке (Номенклатура, Код, Кількість)
                for i, cell in enumerate(row_clean):
                    if any(x in cell for x in ["номенклатура", "назва", "товар"]):
                        col_map["name"] = i
                    elif any(x in cell for x in ["код", "артикул"]):
                        col_map["sku"] = i
                    elif any(x in cell for x in ["кількість", "кол-во", "кол"]):
                        col_map["qty"] = i
                        
                    elif any(x in cell for x in ["штрих", "barcode", "ean"]):
                        col_map["barcode"] = i

                # 2. Теперь ищем по второй строке (Ціна, Од.)
                for i, cell in enumerate(next_row):
                    if "ціна" in cell or "цена" in cell:
                        col_map["price"] = i
                    elif any(x in cell for x in ["од.", "од", "ед."]):
                        col_map["unit"] = i

                # Заполняем дефолты, если что-то упустили
                if "name" in col_map and "price" in col_map:
                    if "total" not in col_map:
                        col_map["total"] = col_map["price"] # Если нет Суммы, приравняем к Цене
                    
                    # 🔥 КРИТИЧЕСКИ ВАЖНО: Перезаписываем индексы в контексте,
                    # чтобы TableEngine знал, что данные идут строго ПОСЛЕ второй строки шапки
                    if hasattr(self, "context") and self.context:
                        self.context["header_index"] = next_idx
                        self.context["column_map"] = col_map

                    return col_map
        return None

    # =========================
    # ИСПРАВЛЕННЫЙ СБОР ТОВАРОВ
    # =========================
    def extract_items(self, rows, context):
            # Безопасное извлечение col_map из context (работает и со словарем, и с объектом)
            col_map = None
            if isinstance(context, dict):
                col_map = context.get("column_map")
            else:
                col_map = getattr(context, "column_map", None)

            # Если мапы еще нет — генерируем её
            if not col_map:
                col_map = self.find_column_map(rows)

            # Синхронизируем локальный context для передачи в TableEngine
            if isinstance(context, dict):
                context["column_map"] = col_map
                if "header_index" not in context:
                    context["header_index"] = next((i for i, r in enumerate(rows[:20]) if "номенклатура" in " ".join(str(c).lower() for c in r)), 0) + 1
            
            # Запускаем TableEngine
            engine = TableEngine(rows, context)
            result = engine.run() or {}
            items = result.get("items") or []

            # 🚀 Если TableEngine выдал по нулям — в дело вступает наш бронебойный fallback
            if not items:
                items = self._fallback_extract_items(rows, col_map or {})

            valid_items = []
            for idx, item in enumerate(items, start=1):
                name = item.get("name", "").strip()
                sku = item.get("sku", "").strip()
                
                # Фильтруем технический мусор прайса
                if not name or (name.isupper() and not sku) or "прайс-лист" in name.lower():
                    continue

                # Парсинг цены
                raw_price = item.get("price")
                price = 0.0
                if raw_price is not None:
                    cleaned_price = re.sub(r'[^\d\.,]', '', str(raw_price)).replace(',', '.')
                    try:
                        price = float(cleaned_price)
                    except:
                        continue

                if price <= 0:
                    continue

                # Парсинг количества
                raw_qty = item.get("qty")
                qty = 1.0
                if raw_qty is not None:
                    try:
                        qty = float(str(raw_qty).replace(',', '.'))
                    except:
                        qty = 1.0
                        
                        
                # Парсинг и очистка штрихкода (если колонка найдена)
                raw_barcode = item.get("barcode", "").strip()
                barcode = None
                if raw_barcode:
                    # Убираем .0 в конце, если Excel превратил штрихкод во float
                    if raw_barcode.endswith(".0"):
                        raw_barcode = raw_barcode[:-2]
                    # Оставляем только цифры
                    barcode = re.sub(r'\D', '', raw_barcode)

                valid_items.append({
                    "position": idx,
                    "sku": str(sku).split('.')[0] if sku else "", 
                    "barcode": barcode, # 🔥 Теперь штрихкод летит в общую структуру
                    "name": name,
                    "qty": qty, 
                    "unit": item.get("unit") or "шт.",
                    "price": price,
                    "total": item.get("total") or (qty * price)
                })

            return valid_items
    def _fallback_extract_items(self, rows, col_map):
        """Резервный сборщик на случай, если TableEngine споткнулся о пустые строки прайса"""
        items = []
        name_idx = col_map.get("name")
        price_idx = col_map.get("price")
        sku_idx = col_map.get("sku")
        qty_idx = col_map.get("qty")
        unit_idx = col_map.get("unit")

        if name_idx is None or price_idx is None:
            return items

        start_capturing = False
        for row in rows:
            if not row:
                continue
            row_str = " ".join(str(c).lower() for c in row if c)
            
            if "номенклатура" in row_str:
                start_capturing = True
                continue
            
            if start_capturing:
                if len(row) <= max(name_idx, price_idx):
                    continue
                
                name = str(row[name_idx]).strip() if row[name_idx] else ""
                price = str(row[price_idx]).strip() if row[price_idx] else ""
                
                if name and price:
                    items.append({
                        "name": name,
                        "price": price,
                        "sku": str(row[sku_idx]).strip() if sku_idx is not None and row[sku_idx] else "",
                        "qty": str(row[qty_idx]).strip() if qty_idx is not None and row[qty_idx] else "1",
                        "unit": str(row[unit_idx]).strip() if unit_idx is not None and row[unit_idx] else "шт."
                    })
        return items

    def extract_totals(self, rows, context):
        """Для пустых прайсов возвращаем дефолтную структуру"""
        return {
            "total": None,
            "vat": 0.0,
            "weight": None,
            "volume": None,
            "summary": None
        }

    def extract_footer(self, rows, context):
        return []

    def extract_warnings(self, rows, context):
        return []

    def extract_signatures(self, rows, context):
        return {"executor": None, "receiver": None}
    
    