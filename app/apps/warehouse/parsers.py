# # app/apps/warehouse/parsers.py
# import os
# import re
# import json
# import pandas as pd
# import pdfplumber
# import pytesseract
# from app.apps.products.models import ProductVariant
# from app.apps.warehouse.models import ProductBarcode, VariantMatchMemory
# from rapidfuzz import process, fuzz
# from PIL import Image, ImageEnhance, ImageFilter
# import numpy as np
# import cv2
# import chardet

# from openpyxl import load_workbook
# import zipfile

# from paddleocr import PaddleOCR ,PPStructure # работает
# # from paddleocr.ppstructure import draw_structure_result  # для таблиц


# VARIANT_CACHE = None

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

#     if ext in [".xlsx", ".xls"]:
#         rows = parse_excel(file)

#     elif ext == ".pdf":
#         rows = parse_pdf(file)

#     else:
#         raise ValueError(f"Unsupported file: {ext}")

#     # enrich ВСЕГДА здесь
#     rows, errors = enrich_rows(rows)

#     data = {
#         "tables": [
#             {
#                 "table_name": "OCR",
#                 "rows": rows
#             }
#         ],
#         "errors": errors
#     }

#     document.extracted_data = data
#     document.save()

#     return rows


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

#     # =========================
#     # 1. SAFE LOAD (xlsx validation)
#     # =========================
#     try:
#         if not is_valid_xlsx(file):
#             return parse_excel_fallback(file)

#         xls = pd.ExcelFile(file, engine="openpyxl")

#     except Exception:
#         # 1C / битые xlsx / fake xls
#         return parse_excel_fallback(file)

#     all_rows = []

#     # =========================
#     # 2. SHEETS LOOP
#     # =========================
#     for sheet_name in xls.sheet_names:

#         try:
#             df = xls.parse(sheet_name, header=None, dtype=str)
#         except:
#             continue

#         df = df.fillna("")

#         # =========================
#         # 3. FIND HEADER
#         # =========================
#         header_row_index = find_header_row(df)

#         # fallback: auto detect header
#         if header_row_index is None:
#             for i in range(len(df)):
#                 row = df.iloc[i].astype(str).tolist()

#                 numbers = sum(bool(re.search(r"\d", str(c))) for c in row)

#                 if numbers >= 2:
#                     header_row_index = max(i - 1, 0)
#                     break

#         if header_row_index is None:
#             continue

#         header = df.iloc[header_row_index].astype(str).tolist()
#         mapping = detect_columns(header)

#         # если нет колонок → пропуск листа
#         if not mapping:
#             continue

#         # =========================
#         # 4. READ ROWS
#         # =========================
#         for i in range(header_row_index + 1, len(df)):

#             row = df.iloc[i].astype(str).tolist()

#             if is_empty_row(row):
#                 continue

#             normalized = normalize_row(row, mapping)
            
            

#             # =========================
#             # 🚨 GARBAGE FILTER (ADD HERE)
#             # =========================
#             if not normalized.get("code") and not normalized.get("name"):
#                 continue

#             code = normalized.get("code")

#             # reject broken excel/binary junk
#             if code:
#                 if len(code) > 50:
#                     continue

#                 if "xl/" in code or "sheet" in code:
#                     continue

#                 if code.startswith("PK"):
#                     continue

#             # optional: name safety
#             name = normalized.get("name")
#             if name and ("xl/" in name or "sheet" in name):
#                 continue

#             # =========================
#             # continue pipeline
#             # =========================

#             # =========================
#             # 5. FILTER GARBAGE
#             # =========================
#             if not normalized.get("code") and not normalized.get("name"):
#                 continue

#             name_l = str(normalized.get("name", "")).lower()

#             if any(x in name_l for x in ["итого", "всього", "total", "subtotal"]):
#                 continue

#             if normalized.get("quantity", 0) == 0 and normalized.get("price", 0) == 0:
#                 continue

#             all_rows.append(normalized)

#     # =========================
#     # 6. VALIDATION
#     # =========================
#     if not all_rows:
#         return parse_excel_fallback(file)

#     # =========================
#     # 7. POST PROCESSING
#     # =========================
#     rows = merge_multiline_rows(all_rows)

#     rows, errors = enrich_rows(rows)

#     return rows, errors















# def is_empty_row(row):
#     if not row:
#         return True

#     return all(str(x).strip() == "" for x in row)

# def find_header_row(df):
#     KEYWORDS = {
#         "code": ["код", "артикул", "sku", "код товара", "номенклатура"],
#         "name": ["назва", "наименование", "товар", "описание"],
#         "qty": ["кількість", "кол", "qty", "к-сть", "количество"],
#         "price": ["ціна", "price", "цена", "стоимость"],
#     }

#     def normalize(text):
#         return str(text).lower().strip()

#     for i in range(min(30, len(df))):
#         row = df.iloc[i].astype(str).fillna("").tolist()
#         row = [normalize(c) for c in row]

#         score = 0
#         matched = set()

#         for cell in row:
#             for group, words in KEYWORDS.items():
#                 if group in matched:
#                     continue

#                 if any(w in cell for w in words):
#                     score += 2
#                     matched.add(group)

#         # 🔥 важно: минимум 2 разных группы колонок
#         if len(matched) >= 2 and score >= 3:
#             return i

#     return None

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
#     "code": [
#         "код", "код товара", "артикул", "артикул товара",
#         "номенклатура", "id товара"
#     ],

#     "name": [
#         "назва", "наименование", "товар", "наименование товара",
#         "description", "позиция", "номенклатура"
#     ],

#     "quantity": [
#         "кількість", "кол", "qty", "к-сть",
#         "количество", "кол-во", "кол-во (шт)", "шт"
#     ],

#     "price": [
#         "ціна", "price", "цена",
#         "цена без ндс", "стоимость", "price за ед", "unit price"
#     ],
# }


# def detect_columns(header):
#     mapping = {}

#     for i, col in enumerate(header):
#         col = str(col).lower().strip()

#         for key, values in COLUMN_MAP.items():
#             match = process.extractOne(col, values, scorer=fuzz.partial_ratio)
#             if match and match[1] > 80:
#                 if key not in mapping:
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


    
# # def normalize_row(row, mapping):
# #     def get(col):
# #         idx = mapping.get(col)
# #         if idx is not None and idx < len(row):
# #             return row[idx]
# #         return None

# #     code = clean_nuls(str(get("code") or ""))
# #     name = clean_nuls(str(get("name") or ""))

# #     quantity = parse_number(get("quantity"))
# #     price = parse_number(get("price"))

# #     return {
# #         "code": code,
# #         "name": name,
# #         "quantity": quantity,
# #         "price": price,
# #     }




# def normalize_row(row, mapping):
#     def get(col):
#         idx = mapping.get(col)
#         if idx is not None and idx < len(row):
#             return row[idx]
#         return None

#     code = hardcore_clean(get("code"))
#     name = hardcore_clean(get("name"))

#     quantity = parse_number(get("quantity"))
#     price = parse_number(get("price"))

#     return {
#         "code": code,
#         "name": name,
#         "quantity": quantity,
#         "price": price,
#     }

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

    
# def merge_multiline_rows(rows):
#     merged = []
#     buffer = None

#     for row in rows:
#         code = str(row.get("code") or "").strip()
#         name = str(row.get("name") or "").strip()
#         qty = row.get("quantity", 0)
#         price = row.get("price", 0)

#         is_new_row = bool(code or qty or price)

#         if is_new_row:
#             if buffer:
#                 merged.append(buffer)
#             buffer = row.copy()
#         else:
#             if buffer:
#                 buffer["name"] = (buffer.get("name", "") + " " + name).strip()

#     if buffer:
#         merged.append(buffer)

#     return merged

# def match_variant(row):
#     code = str(row.get("code") or "").strip()
#     name = str(row.get("name") or "").strip()

#     # 1. пробуем barcode
#     if code:
#         barcode = ProductBarcode.objects.filter(barcode=code).select_related("variant").first()
#         if barcode:
#             # return barcode.variant, 1.0  # максимальная уверенность
#             return barcode.variant.id, 1.0

#     # 2. пробуем exact code (если у тебя SKU в модели)
#     variant = ProductVariant.objects.filter(code=code).first()
#     if variant:
#         return variant, 0.95

#     # 3. fuzzy name
#     variant = find_variant(name, ProductVariant.objects.all())
#     if variant:
#         return variant, 0.8

#     return None, 0.0

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





# # def enrich_rows(rows):
# #     global VARIANT_CACHE

# #     if VARIANT_CACHE is None:
# #         VARIANT_CACHE = build_variant_cache()

# #     enriched = []
# #     errors = []

# #     for row in rows:
# #         row["code"] = clean_nuls(row.get("code"))
# #         row["name"] = clean_nuls(row.get("name"))

# #         variant, confidence = match_variant_learning(
# #             row,
# #             VARIANT_CACHE,
# #             supplier=None
# #         )

# #         # row["variant_id"] = variant.id if variant else None
# #         # row["variant_id"] = variant["id"] if isinstance(variant, dict) else variant
# #         row["variant_id"] = variant
# #         row["confidence"] = confidence

# #         if not variant:
# #             errors.append({
# #                 "type": "NOT_FOUND",
# #                 "row": row
# #             })
# #         elif confidence < 0.85:
# #             errors.append({
# #                 "type": "LOW_CONFIDENCE",
# #                 "row": row
# #             })

# #         enriched.append(row)

# #     return enriched, errors




# def enrich_rows(rows):
#     global VARIANT_CACHE

#     if VARIANT_CACHE is None:
#         VARIANT_CACHE = build_variant_cache()

#     enriched = []
#     errors = []

#     for row in rows:
#         # =========================
#         # CLEAN INPUT
#         # =========================
#         # row["code"] = clean_nuls(row.get("code"))
#         # row["name"] = clean_nuls(row.get("name"))
        
#         row["code"] = hardcore_clean(row.get("code"))
#         row["name"] = hardcore_clean(row.get("name"))

#         # =========================
#         # MATCHING
#         # =========================
#         variant, confidence = match_variant_learning(
#             row,
#             VARIANT_CACHE,
#             supplier=None
#         )

#         # =========================
#         # NORMALIZE OUTPUT (ВАЖНО)
#         # =========================
#         if variant is None:
#             variant_id = None

#         elif isinstance(variant, dict):
#             variant_id = variant.get("id")

#         else:
#             # Django ORM object
#             variant_id = getattr(variant, "id", None)

#         row["variant_id"] = variant_id
#         row["confidence"] = confidence

#         # =========================
#         # ERRORS
#         # =========================
#         if not variant_id:
#             errors.append({
#                 "type": "NOT_FOUND",
#                 "row": row
#             })

#         elif confidence < 0.85:
#             errors.append({
#                 "type": "LOW_CONFIDENCE",
#                 "row": row
#             })
            
            
        

#         enriched.append(row)

#     return enriched, errors






# def hardcore_clean(val):
#     if val is None:
#         return None

#     val = str(val)

#     # 1. убираем null bytes
#     val = val.replace("\x00", "")

#     # 2. вырезаем excel zip мусор
#     if val.startswith("PK"):
#         return None

#     # 3. выкидываем бинарщину
#     if sum(ord(c) < 32 for c in val[:10]) > 2:
#         return None

#     # 4. если это похоже на xml/worksheet — мусор
#     if "xl/" in val or "sheet" in val:
#         return None

#     return val.strip()




# # def hardcore_clean(val):
# #     if val is None:
# #         return None
# #     if isinstance(val, str):
# #         val = val.replace("\x00", "")
# #         val = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", val)
# #         return val.strip()
# #     return val








# def build_variant_cache():
#     """
#     Кэш всех вариантов товаров один раз (ускоряет парсинг в десятки раз)
#     """

#     variants = ProductVariant.objects.all().values(
#         "id",
#         "variant_name",
#         "code",
#         "barcode",
#     )

#     cache = {
#         "by_id": {},
#         "names": [],
#         "code": {},       # SKU / internal code
#         "barcode": {},    # EAN / barcode
#     }

#     for v in variants:
#         vid = v["id"]

#         cache["by_id"][vid] = v

#         # name index (для fuzzy match)
#         if v.get("variant_name"):
#             cache["names"].append(v["variant_name"])

#         # SKU (code)
#         code = v.get("code")
#         if code:
#             cache["code"][code.strip()] = vid

#         # barcode (EAN)
#         barcode = v.get("barcode")
#         if barcode:
#             cache["barcode"][barcode.strip()] = vid

#     return cache

# def match_variant_learning(row, cache, supplier=None):
#     code = str(row.get("code") or "").strip()
#     name = str(row.get("name") or "").strip()

#     # =========================
#     # 1. MEMORY (самый приоритет)
#     # =========================
#     memory_qs = VariantMatchMemory.objects.filter(supplier=supplier)

#     if code:
#         memory = memory_qs.filter(raw_code=code).select_related("variant").first()
#         if memory:
#             memory.hit_count = (memory.hit_count or 0) + 1
#             memory.save(update_fields=["hit_count", "last_used"])
#             return memory.variant, 1.0

#     if name:
#         memory = memory_qs.filter(raw_name=name).select_related("variant").first()
#         if memory:
#             memory.hit_count = (memory.hit_count or 0) + 1
#             memory.save(update_fields=["hit_count", "last_used"])
#             return memory.variant_id, 1.0
#             # return memory.variant, 1.0

#     # =========================
#     # 2. BARCODE MATCH (100%)
#     # =========================
#     if code:
#         variant_id = cache["barcode"].get(code)
#         if variant_id:
#             return cache["by_id"][variant_id], 1.0

#         barcode = ProductBarcode.objects.filter(code=code).select_related("variant").first()
#         if barcode:
#             return barcode.variant_id, 1.0
#             # return barcode.variant, 1.0v
            

#     # =========================
#     # 3. CODE (SKU) MATCH (95%)
#     # =========================
#     if code:
#         variant_id = cache["code"].get(code)
#         if variant_id:
#             return cache["by_id"][variant_id]["id"], 0.95
#             # return cache["by_id"][variant_id], 0.95

#     # =========================
#     # 4. FUZZY NAME MATCH
#     # =========================
#     best_variant = None
#     best_score = 0

#     for variant_id, v in cache["by_id"].items():
#         vname = v.get("variant_name") or ""
#         if not vname or not name:
#             continue

#         score = fuzz.token_sort_ratio(name, vname)

#         if score > best_score:
#             best_score = score
#             best_variant = v

#     if best_variant and best_score > 80:
#         return best_variant, best_score / 100

#     return None, 0.0


def learn_variant_match(row, variant, supplier=None):
    code = str(row.get("code") or "").strip()
    name = str(row.get("name") or "").strip()

    obj, created = VariantMatchMemory.objects.get_or_create(
        supplier=supplier,
        raw_code=code,
        raw_name=name,
        defaults={
            "variant": variant,
            "confidence": 1.0
        }
    )

    if not created:
        obj.hit_count += 1
        obj.variant = variant
        obj.save()
        
        
        
        
        
        
        
        
        
# def is_valid_xlsx(file_path):
#     try:
#         with zipfile.ZipFile(file_path, 'r') as z:
#             return "xl/workbook.xml" in z.namelist()
#     except:
#         return False

# def is_binary_file(file_path):
#     try:
#         with open(file_path, "rb") as f:
#             chunk = f.read(2048)
#             return b"\x00" in chunk
#     except:
#         return True

# def parse_excel_fallback(file):

#     # =========================
#     # 1. TRY REAL EXCEL FIRST (even broken)
#     # =========================
#     try:
#         df = pd.read_excel(file, header=None, engine="openpyxl")
#         return normalize_fallback_df(df)
#     except:
#         pass

#     # =========================
#     # 2. TRY XLS (old excel)
#     # =========================
#     try:
#         df = pd.read_excel(file, header=None, engine="xlrd")
#         return normalize_fallback_df(df)
#     except:
#         pass

#     # =========================
#     # 3. TRY AUTO-DETECT ENCODING CSV
#     # =========================
#     try:
#         raw = open(file, "rb").read()
#         enc = chardet.detect(raw)["encoding"] or "utf-8"

#         text = raw.decode(enc, errors="ignore")

#         rows = []
#         for line in text.splitlines():
#             parts = re.split(r"[;\t,|]", line)
#             parts = [p.strip() for p in parts if p.strip()]

#             if len(parts) >= 2:
#                 rows.append({
#                     "code": parts[0],
#                     "name": " ".join(parts[1:-2]) if len(parts) > 2 else parts[1],
#                     "quantity": 0,
#                     "price": 0
#                 })

#         return rows

#     except Exception:
#         return []



# def normalize_fallback_df(df):
#     rows = []

#     df = df.fillna("")

#     for row in df.values.tolist():
#         row = [str(x).strip() for x in row if str(x).strip()]

#         if len(row) < 2:
#             continue

#         rows.append({
#             "code": row[0],
#             "name": " ".join(row[1:-2]) if len(row) > 2 else row[1],
#             "quantity": 0,
#             "price": 0
#         })

#     return rows



# def clean_nuls(val):
#     if val is None:
#         return None
#     if isinstance(val, str):
#         return val.replace("\x00", "").strip()
#     return val




