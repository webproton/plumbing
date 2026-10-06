# parsers/core/loader.py
from openpyxl import load_workbook
import pandas as pd
import xml.etree.ElementTree as ET
import os




def parse_yml(file_path):
    tree = ET.parse(file_path)
    root = tree.getroot()

    ns = {}

    items = []

    for offer in root.findall(".//offer"):
        item = {
            "id": offer.get("id"),
            "available": offer.get("available"),
        }

        for child in offer:
            tag = child.tag.lower()

            if tag == "name":
                item["name"] = child.text

            elif tag == "price":
                item["price"] = float(child.text)

            elif tag == "currencyid":
                item["currency"] = child.text

            elif tag == "categoryid":
                item["category_id"] = child.text

        items.append(item)

    return items


def load_xml_rows(file_path):
    """Fallback для старых XML таблиц (например, выгрузки типа Spreadsheet XML)"""
    tree = ET.parse(file_path)
    root = tree.getroot()
    rows = []

    for row in root.findall(".//Row"):
        cells = []
        for cell in row:
            text = cell.text or "".join(cell.itertext()).strip()
            cells.append(text)
        if any(cells):
            rows.append(cells)
    return rows


def load_rows(file_path):
    """
    Основная функция загрузки документов. 
    Всегда возвращает массив строк (список списков).
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Файл не найден: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()
    
    # ==========================================
    # ОБРАБОТКА XML / YML ФОРМАТОВ
    # ==========================================
    if ext in [".xml", ".yml"]:
        try:
            tree = ET.parse(file_path)
            root = tree.getroot()
            
            # Если это YML-фид (как у Секвои) — вызываем правильный конвертер в строки
            if root.tag == "yml_catalog":
                return _load_xml_as_rows(file_path)
            
            # Если другой XML — пробуем прочитать как плоскую XML-таблицу
            return load_xml_rows(file_path)
        except Exception as e:
            raise ValueError(f"Не удалось распарсить XML структуру: {e}")

    # ==========================================
    # ОБРАБОТКА XLSX (openpyxl)
    # ==========================================
    if ext == ".xlsx":
        try:
            wb = load_workbook(file_path, data_only=True)
            ws = wb.active
            return list(ws.iter_rows(values_only=True))
        except Exception:
            pass

    # ==========================================
    # СТАНДАРТНЫЙ FALLBACK ДЛЯ XLS / XLSX (pandas)
    # ==========================================
    try:
        df = pd.read_excel(file_path, header=None, engine="openpyxl")
    except Exception:
        try:
            df = pd.read_excel(file_path, header=None, engine="calamine")
        except Exception:
            raise ValueError(f"Не поддерживаемый формат Excel или файл поврежден: {file_path}")

    return df.fillna("").values.tolist()



def _load_xml_as_rows(file_path: str):
    """
    Конвертирует XML (YML-каталог) в виртуальную Excel-таблицу (массив строк),
    чтобы базовые парсеры могли читать его без изменения логики.
    """
    rows = []
    try:
        tree = ET.parse(file_path)
        root = tree.getroot()
    except Exception as e:
        raise ValueError(f"Ошибка синтаксиса XML в файле {file_path}: {e}")

    # 1. Извлекаем дату из корня (если это yml_catalog)
    catalog_date = root.get("date", "")
    
    # 2. Ищем блок информации о магазине / компании
    shop = root.find("shop")
    shop_name = shop.find("name").text if shop is not None and shop.find("name") is not None else ""
    company = shop.find("company").text if shop is not None and shop.find("company") is not None else ""
    
    # Генерируем "виртуальную шапку" документа (чтобы detect.py и extract_meta нашли поставщика)
    rows.append(["Постачальник / Компанія:", company or shop_name])
    rows.append(["Дата документа:", catalog_date])
    rows.append(["Тип файлу:", "XML розвантаження B2B"])
    rows.append([]) # Пустая строка-разделитель
    rows.append([])

    # Собираем категории в словарь для быстрого поиска имен по ID
    categories_map = {}
    if shop is not None:
        cats = shop.find("categories")
        if cats is not None:
            for cat in cats.findall("category"):
                cat_id = cat.get("id")
                if cat_id:
                    categories_map[cat_id] = cat.text

    # 3. Генерируем виртуальную шапку таблицы товаров
    # Задаем фиксированный порядок, к которому привык наш TableEngine
    header_row = ["Номенклатура (Товар)", "Код (SKU)", "Кількість", "Ціна", "Од. вим.", "Категорія"]
    rows.append(header_row)

    # 4. Парсим сами товары (в YML они лежат в <offers> -> <offer>)
    offers_block = shop.find("offers") if shop is not None else root.find(".//offers")
    
    if offers_block is not None:
        for offer in offers_block.findall("offer"):
            # Вытаскиваем данные из тегов и атрибутов
            sku = offer.get("id") or offer.find("vendorCode").text if offer.find("vendorCode") is not None else ""
            name = offer.find("name").text if offer.find("name") is not None else ""
            price = offer.find("price").text if offer.find("price") is not None else "0"
            currency = offer.find("currencyId").text if offer.find("currencyId") is not None else "UAH"
            cat_id = offer.find("categoryId").text if offer.find("categoryId") is not None else ""
            category_name = categories_map.get(cat_id, "")

            # Формируем виртуальную строку товара
            # Если цена указана в USD/EUR, можно прямо тут приклеить валюту к цене, 
            # наш мягкий парсер цен в extract_items её очистит.
            price_str = f"{price} {currency}"
            
            product_row = [
                name,          # name
                sku,           # sku
                "1.0",         # qty (в прайсах XML обычно остатка нет или он > 0, ставим 1)
                price_str,     # price
                "шт.",         # unit
                category_name  # Доп. инфо
            ]
            rows.append(product_row)

    print(f"XML успешно сконвертирован: создано {len(rows)} виртуальных строк.")
    return rows