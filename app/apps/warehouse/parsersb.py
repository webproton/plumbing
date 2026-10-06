# # app/apps/warehouse/parsers.py
# import os
# import re
# import json
# import pandas as pd
# import pdfplumber
# import pytesseract
# from rapidfuzz import process, fuzz
# import pandas as pd
# from PIL import Image, ImageEnhance, ImageFilter
# import numpy as np
# import cv2

# from paddleocr import PaddleOCR ,PPStructure # работает
# # from paddleocr.ppstructure import draw_structure_result  # для таблиц

# # для совместимости старого кода PaddleOCR
# if not hasattr(np, 'int'):
#     np.int = int
# if not hasattr(np, 'float'):
#     np.float = float

# # Модель для русского, украинского и английского
# # Инициализируем один раз (лучше вынести в модуль)
# ocr_ru = PaddleOCR(use_angle_cls=True, lang="ru", show_log=False)
# ocr_uk = PaddleOCR(use_angle_cls=True, lang="uk", show_log=False)
# ocr_en = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)

# def get_ocr_reader(text_sample: str = ""):
#     """Простой выбор модели по наличию кириллицы"""
#     if any(ord(c) > 1000 for c in text_sample[:200]):  # грубо проверяем кириллицу
#         return ocr_ru if 'а' in text_sample or 'і' in text_sample else ocr_uk
#     return ocr_en

# # =========================
# # UNIVERSAL ENTRY POINT
# # =========================

# def extract_document_data(document):
#     file = document.file.path
#     ext = os.path.splitext(file)[1].lower()

#     if ext in [".jpg", ".jpeg", ".png"]:
#         header, rows = parse_image_invoice(file)
#         document.document_number = header.get("document_number")
#         document.supplier = header.get("supplier")
#         # document.date = ... можно добавить
#         document.save()

#     elif ext in [".xlsx", ".xls"]:
#         rows = parse_excel(file)

#     elif ext == ".pdf":
#         rows = parse_pdf(file) # или конвертировать PDF в изображения и использовать OCR

#     elif ext in [".jpg", ".jpeg", ".png"]:
#         rows = parse_image(file)

#     else:
#         raise ValueError(f"Unsupported file: {ext}")

#     data = {
#         "tables": [
#             {
#                 "table_name": "OCR",
#                 "rows": rows
#             }
#         ]
#     }

#     document.extracted_data = data
#     document.save()

#     return rows

# # =========================
# # OCR IMAGE
# # =========================




# def parse_image(file):
#     img = Image.open(file).convert("L")  # ч/б для лучшего OCR
#     img = img.point(lambda x: 0 if x < 140 else 255)  # пороговая фильтрация
#     text = pytesseract.image_to_string(img, lang="rus+ukr+eng")
#     # используем новый парсер
#     return parse_invoice_text(text)



# # =========================
# # PARSER FOR OCR INVOICE TEXT
# # =========================



# def parse_invoice_text(text):
#     rows = []
#     lines = text.split("\n")

#     for line in lines:
#         line = line.strip()
#         if not line:
#             continue

#         # очищаем мусор OCR
#         clean = re.sub(r"[|()\[\]]", " ", line)
#         clean = re.sub(r"\s+", " ", clean)

#         # ищем числа
#         numbers = re.findall(r"\d+[.,]?\d*", clean)

#         # нужно минимум: код + qty + price
#         if len(numbers) < 3:
#             continue

#         code = numbers[0]
#         quantity = numbers[-2]
#         price = numbers[-1]

#         # название = между кодом и числами
#         name = clean.replace(code, "", 1)
#         name = name.rsplit(quantity, 1)[0]
#         name = name.strip()

#         rows.append({
#             "code": code,
#             "name": name,
#             "quantity": float(quantity.replace(",", ".")),
#             "price": float(price.replace(",", ".")),
#         })

#     return rows



# # =========================
# # EXCEL
# # =========================

# def parse_excel(file):
#     df = pd.read_excel(file)

#     rows = []
#     for _, row in df.iterrows():
#         rows.append(row.to_dict())

#     return rows


# # =========================
# # TEXT TABLE PARSER (OCR)
# # =========================

# def parse_text_table(text):
#     lines = text.split("\n")
#     rows = []

#     for line in lines:
#         line = line.strip()
#         if not line:
#             continue

#         parts = re.split(r"\s{2,}|\t", line)

#         if len(parts) >= 3:
#             rows.append(parts)

#     return rows


# # =========================
# # AUTO COLUMN DETECTION
# # =========================

# COLUMN_MAP = {
#     "code": ["код", "артикул", "sku", "code"],
#     "name": ["назва", "наименование", "товар", "name"],
#     "quantity": ["кількість", "кол", "qty", "к-сть"],
#     "price": ["ціна", "price", "цена"],
# }





# def detect_columns(header):
#     mapping = {}

#     for i, col in enumerate(header):
#         col = str(col).lower()

#         for key, values in COLUMN_MAP.items():
#             for v in values:
#                 if v in col:
#                     mapping[key] = i

#     return mapping

# # =========================
# # NORMALIZE
# # =========================

# def normalize_rows(rows):
#     normalized = []

#     if not rows:
#         return normalized

#     header = rows[0]
#     mapping = detect_columns(header)

#     for row in rows[1:]:

#         def get(col):
#             idx = mapping.get(col)
#             if idx is not None and idx < len(row):
#                 return row[idx]
#             return None

#         normalized.append({
#             "code": get("code"),
#             "name": get("name"),
#             "quantity": parse_number(get("quantity")),
#             "price": parse_number(get("price")),
#         })

#     return normalized



# # =========================
# # PARSE NUMBERS
# # =========================

# def parse_number(val):
#     if val is None:
#         return 0

#     val = str(val).replace(",", ".")
#     m = re.findall(r"\d+\.?\d*", val)

#     return float(m[0]) if m else 0


# # =========================
# # FUZZY MATCH
# # =========================

# def find_variant(name, queryset):

#     names = list(queryset.values_list("variant_name", flat=True))

#     match = process.extractOne(
#         name,
#         names,
#         scorer=fuzz.token_sort_ratio
#     )

#     if match and match[1] > 80:
#         return queryset.filter(variant_name=match[0]).first()

#     return None

# def parse_excel_invoice(file):
#     '''Парсер Excel накладной'''
#     df = pd.read_excel(file)

#     rows = []

#     for _, row in df.iterrows():
#         rows.append({
#             "code": str(row.get("Код товара", "")),
#             "name": row.get("Номенклатура"),
#             "quantity": float(row.get("Количество", 0)),
#             "price": float(row.get("Цена", 0)),
#             "sum": float(row.get("Сумма", 0)),
#         })

#     return {
#         "tables": [
#             {
#                 "table_name": "Товары",
#                 "rows": rows
#             }
#         ]
#     }
    
    
    
    
# def parse_pdf(file):
#     '''alt parser'''
#     rows = []

#     with pdfplumber.open(file) as pdf:
#         for page in pdf.pages:
#             table = page.extract_table()
#             if table:
#                 rows += table

#     return rows
    


# def parse_pdf_invoice(file):
#     '''Парсер PDF накладной'''
#     rows = []

#     with pdfplumber.open(file) as pdf:
#         for page in pdf.pages:
#             table = page.extract_table()

#             if not table:
#                 continue

#             for row in table[1:]:
#                 rows.append({
#                     "code": row[0],
#                     "name": row[1],
#                     "quantity": float(row[2] or 0),
#                     "price": float(row[3] or 0),
#                     "sum": float(row[4] or 0),
#                 })

#     return {
#         "tables": [
#             {
#                 "table_name": "PDF Table",
#                 "rows": rows
#             }
#         ]
#     }
    
    
# # =========================
# # IMPROVED IMAGE PARSER (PaddleOCR)
# # =========================
# # =========================
# # IMPROVED PREPROCESSING (самое важное!)
# # =========================
# def preprocess_image(file_path):
#     """Улучшенная предобработка специально под фото накладных"""
#     img = cv2.imread(file_path)
#     if img is None:
#         img = np.array(Image.open(file_path).convert("RGB"))
#         img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)

#     gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
#     # 1. Выравнивание освещения
#     gray = cv2.equalizeHist(gray)
    
#     # 2. Удаление шума
#     gray = cv2.fastNlMeansDenoising(gray, h=10)
    
#     # 3. Резкость (очень помогает при размытых фото)
#     kernel = np.array([[-1, -1, -1],
#                        [-1,  9, -1],
#                        [-1, -1, -1]])
#     gray = cv2.filter2D(gray, -1, kernel)
    
#     # 4. Лёгкое увеличение контраста
#     gray = cv2.convertScaleAbs(gray, alpha=1.2, beta=10)
    
#     return gray  # ← возвращаем gray, а не binary (для PaddleOCR лучше)


# # =========================
# # FIXED parse_image_invoice
# # =========================
# def parse_image_invoice(file_path):
#     """
#     Основная функция. Теперь:
#     - используем только ru + uk модели
#     - понижаем порог confidence
#     - выводим полный debug в логи
#     - улучшенный extract_rows_from_text
#     """
#     processed = preprocess_image(file_path)

#     # Для украинско-русских накладных ru и uk модели работают лучше всего
#     results_ru = ocr_ru.ocr(processed, cls=True)
#     results_uk = ocr_uk.ocr(processed, cls=True)

#     # Берём тот результат, где больше текста (обычно ru или uk)
#     best_result = results_ru if len(results_ru[0]) > len(results_uk[0]) else results_uk

#     print("=== OCR DEBUG START ===")
#     print("OCR raw output (ru):", results_ru)   # оставляем для тебя

#     lines = []
#     full_text = ""
#     for line in best_result[0]:
#         text_data = line[1]
#         if isinstance(text_data, (list, tuple)) and len(text_data) >= 2:
#             text = str(text_data[0]).strip()
#             conf = text_data[1]
#         else:
#             text = str(text_data).strip()
#             conf = 0.5

#         if text and conf >= 0.35:          # ← понизили порог!
#             full_text += text + "\n"
#             lines.append(text)

#     print("FULL TEXT (что увидел OCR):")
#     print(full_text)
#     print(f"Найдено строк: {len(lines)}")
#     print("=== OCR DEBUG END ===")

#     header = extract_header(lines)
#     rows = extract_rows_from_text(lines)   # ← новая версия ниже

#     return header, rows
# def extract_header(lines):
#     header = {"document_number": None, "date": None, "supplier": None}
#     text_lower = "\n".join(lines).lower()

#     # Номер накладной
#     for pattern in [r"№\s*(\S+)", r"номер\s*[:\-]?\s*(\S+)", r"invoice\s*no\.?\s*(\S+)", r"накладна\s*№\s*(\S+)"]:
#         m = re.search(pattern, text_lower)
#         if m:
#             header["document_number"] = m.group(1).strip()
#             break

#     # Дата
#     date_match = re.search(r"\d{1,2}[.\-/]\d{1,2}[.\-/]\d{2,4}", "\n".join(lines))
#     if date_match:
#         header["date"] = date_match.group(0)

#     # Поставщик (примерно)
#     for i, line in enumerate(lines):
#         low = line.lower()
#         if any(k in low for k in ["поставщик", "постачальник", "supplier", "vendor"]):
#             if i+1 < len(lines):
#                 header["supplier"] = lines[i+1].strip()
#             break

#     return header


# def extract_rows_from_text(lines):
#     """Улучшенный парсер — работает даже при плохом OCR"""
#     rows = []
#     for line in lines:
#         line_clean = re.sub(r"[|()\[\]«»!?:]", " ", line).strip()
#         if len(line_clean) < 6:
#             continue

#         # Ищем ВСЕ числа в строке
#         numbers = re.findall(r"\b\d+[.,]?\d*\b", line_clean)
#         if len(numbers) < 2:        # минимум код + цена/кол-во
#             continue

#         code = numbers[0]
#         price = numbers[-1]         # последнее число почти всегда цена или сумма
#         quantity = numbers[-2] if len(numbers) >= 3 else "1"

#         # Название — всё, что между кодом и последними числами
#         name_part = line_clean.replace(code, "", 1)
#         for num in [quantity, price]:
#             if num in name_part:
#                 name_part = name_part.rsplit(num, 1)[0]

#         name = re.sub(r"\s+", " ", name_part).strip()

#         try:
#             rows.append({
#                 "code": code,
#                 "name": name or "Не распознано",
#                 "quantity": float(quantity.replace(",", ".")),
#                 "price": float(price.replace(",", ".")),
#                 "sum": 0.0
#             })
#         except:
#             continue

#     # Дополнительно: если нашли строку с "Всього" / "Bcero" — это итог, можно пропустить

#     return [r for r in rows if not any(x in r["name"].lower() for x in ["всього", "bcero", "итого"])]






# # def parse_invoice_text(text):
#     # """
#     # Простое извлечение товаров из OCR накладной
#     # Ищем строки с код, название, количество и цену
#     # """
#     # rows = []

#     # # разбиваем на строки
#     # lines = text.split("\n")
#     # for line in lines:
#     #     line = line.strip()
#     #     if not line:
#     #         continue

#     #     # ищем код (число в начале строки)
#     #     match = re.match(r"^(\d+)\s+(.*)\s+(\d+[\.,]?\d*)\s+(\d+[\.,]?\d*)", line)
#     #     if match:
#     #         code, name, quantity, price = match.groups()
#     #         rows.append({
#     #             "code": code.strip(),
#     #             "name": name.strip(),
#     #             "quantity": float(quantity.replace(",", ".")),
#     #             "price": float(price.replace(",", ".")),
#     #         })

#     # return rows
















# # def parse_image_invoice(file_path):
# #     """
# #     Извлекает данные накладной с фото/скана с помощью PaddleOCR PPStructure.
# #     Возвращает:
# #         header: dict с номером документа, датой, поставщиком
# #         rows: список товаров с code, name, quantity, price, sum
# #     """
# #     result = ocr(file_path)

# #     header = {
# #         "document_number": None,
# #         "date": None,
# #         "supplier": None
# #     }

# #     rows = []

# #     for item in result:
# #         if item['type'] == 'text':
# #             text = item['text'].strip()
# #             low_text = text.lower()

# #             # номер накладной
# #             if "накладна" in low_text or "накладная" in low_text:
# #                 m = re.search(r"№\s*(\d+)", text)
# #                 if m:
# #                     header["document_number"] = m.group(1)

# #             # дата
# #             m_date = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
# #             if m_date:
# #                 header["date"] = m_date.group()

# #             # поставщик
# #             if "поставщик" in low_text or "supplier" in low_text:
# #                 header["supplier"] = text.split(":")[-1].strip()

# #         elif item['type'] == 'table':
# #             table = item['cells']
# #             if not table:
# #                 continue

# #             # первая строка — заголовок
# #             header_row = table[0]
# #             col_map = {}
# #             for i, cell in enumerate(header_row):
# #                 cell_text = str(cell).lower() if cell else ""
# #                 if "код" in cell_text or "артикул" in cell_text or "sku" in cell_text:
# #                     col_map['code'] = i
# #                 elif "назв" in cell_text or "товар" in cell_text or "name" in cell_text:
# #                     col_map['name'] = i
# #                 elif "кол" in cell_text or "qty" in cell_text or "к-сть" in cell_text:
# #                     col_map['quantity'] = i
# #                 elif "цена" in cell_text or "price" in cell_text:
# #                     col_map['price'] = i
# #                 elif "сум" in cell_text or "total" in cell_text:
# #                     col_map['sum'] = i

# #             # обработка строк таблицы
# #             for row in table[1:]:
# #                 def get(col):
# #                     idx = col_map.get(col)
# #                     if idx is not None and idx < len(row):
# #                         return row[idx]
# #                     return None

# #                 # безопасное приведение к числу
# #                 def safe_float(val):
# #                     try:
# #                         return float(str(val).replace(",", "."))
# #                     except (ValueError, TypeError):
# #                         return 0.0

# #                 rows.append({
# #                     "code": str(get("code") or ""),
# #                     "name": str(get("name") or ""),
# #                     "quantity": safe_float(get("quantity")),
# #                     "price": safe_float(get("price")),
# #                     "sum": safe_float(get("sum")),
# #                 })

# #     return header, rows





































# # def parse_image(file):
# #     img = Image.open(file)
# #     text = pytesseract.image_to_string(img, lang="rus+ukr+eng")
# #     return parse_text_table(text)

# # def parse_invoice_text(text):
# #     """
# #     Ищет строки вида:
# #     код | наименование | количество | цена | сумма
# #     """
# #     rows = []
# #     lines = text.split("\n")
    
# #     # шаблон: код, наименование, количество, цена, сумма
# #     pattern = re.compile(
# #         r"(\d+)\s+(.+?)\s+([\d,\.]+)\s*шт?\s*[\|\)]?\s*([\d,\.]+)\s*[\|\)]?\s*([\d,\.]+)"
# #     )
    
# #     for line in lines:
# #         match = pattern.search(line)
# #         if match:
# #             code, name, qty, price, total = match.groups()
# #             rows.append({
# #                 "code": code.strip(),
# #                 "name": name.strip(),
# #                 "quantity": float(qty.replace(",", ".")),
# #                 "price": float(price.replace(",", ".")),
# #                 "sum": float(total.replace(",", "."))
# #             })
    
# #     return rows


# # def parse_image_invoice(file_path):
# #     """
# #     Извлекает данные накладной с фото/скана с помощью PaddleOCR PPStructure.
# #     Возвращает:
# #         header: dict с номером документа, датой, поставщиком
# #         rows: список товаров с code, name, quantity, price
# #     """
# #     result = ocr(file_path)  # результат структуры документа

# #     header = {
# #         "document_number": None,
# #         "date": None,
# #         "supplier": None
# #     }

# #     rows = []

# #     # PPStructure возвращает список таблиц и текста
# #     for item in result:
# #         # 'type': 'text' / 'table'
# #         if item['type'] == 'text':
# #             text = item['text'].strip().lower()
# #             # ищем номер накладной
# #             if "накладная" in text:
# #                 import re
# #                 m = re.search(r"№\s*(\d+)", text)
# #                 if m:
# #                     header["document_number"] = m.group(1)
# #             # ищем дату в формате dd.mm.yyyy
# #             m_date = re.search(r"\d{2}\.\d{2}\.\d{4}", text)
# #             if m_date:
# #                 header["date"] = m_date.group()
# #             # ищем поставщика
# #             if "поставщик" in text:
# #                 header["supplier"] = text.split(":")[-1].strip()

# #         elif item['type'] == 'table':
# #             table = item['cells']  # список списков ячеек
# #             if not table:
# #                 continue
# #             # допустим, первая строка — заголовок
# #             header_row = table[0]
# #             # определяем индексы колонок
# #             col_map = {}
# #             for i, cell in enumerate(header_row):
# #                 cell_text = str(cell).lower()
# #                 if "код" in cell_text or "артикул" in cell_text:
# #                     col_map['code'] = i
# #                 elif "назв" in cell_text or "товар" in cell_text:
# #                     col_map['name'] = i
# #                 elif "кол" in cell_text or "qty" in cell_text:
# #                     col_map['quantity'] = i
# #                 elif "цена" in cell_text or "price" in cell_text:
# #                     col_map['price'] = i

# #             for row in table[1:]:
# #                 def get(col):
# #                     idx = col_map.get(col)
# #                     if idx is not None and idx < len(row):
# #                         return row[idx]
# #                     return None

# #                 rows.append({
# #                     "code": get("code"),
# #                     "name": get("name"),
# #                     "quantity": float(str(get("quantity") or "0").replace(",", ".")),
# #                     "price": float(str(get("price") or "0").replace(",", "."))
# #                 })

# #     return header, rows
    
    
    
# # def extract_invoice_header(text): for pyteseract
# #     """
# #     Ищем номер накладной, дату и поставщика
# #     """
# #     header = {}
# #     lines = text.split("\n")

# #     for line in lines:
# #         line = line.strip()
# #         if "накладная" in line.lower():
# #             m = re.search(r"№\s*(\d+)", line)
# #             if m:
# #                 header["document_number"] = m.group(1)
# #         if re.search(r"\d{2}\.\d{2}\.\d{4}", line):
# #             header["date"] = re.search(r"\d{2}\.\d{2}\.\d{4}", line).group()
# #         if "поставщик" in line.lower():
# #             header["supplier"] = line.split(":")[-1].strip()

# #     return header

