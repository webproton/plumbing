# parsers/detect.py


import re
from parsers.core.text_utils import build_text

# =========================
# SUPPLIER DETECTION
# =========================


# Ключевые слова в шапке накладной → код поставщика (совпадает с Supplier.code)
SUPPLIER_PATTERNS = {
    "aquadom": [
        "аквадом", "aquadom", "аква дом", 
        "тов \"аквадом\"", "фоп аквадом", "аква-дом"
    ],
    "presto": [ 
        "presto", "presto-ps", "престо", 
        "дзюба олена", "фоп дзюба", "дзюба"
    ],
    "santan": [
        "santan", "сантен", "сантан"
    ],
    # Сюда добавляй новых поставщиков в будущем
}


def detect_supplier(rows):
    # Извлекаем текст первых 30 строк и переводим в нижний регистр
    text = build_text(rows[:30]).lower()  

    # 🔥 ИСПРАВЛЕНИЕ: Цикл идет по нашему глобальному SUPPLIER_PATTERNS
    for supplier_code, keys in SUPPLIER_PATTERNS.items():
        if any(k in text for k in keys):
            return supplier_code

    return "default"

# =========================
# BUYER DETECTION
# =========================

def detect_buyer(rows):
    text = build_text(rows).lower()

    if any(x in text for x in ["балабанов", "березинский"]):
        return "balabanov"

    return "unknown"


# =========================
# DOCUMENT TYPE
# =========================

def detect_document_type(rows):
    text = build_text(rows)

    if "расходная накладная" in text:
        return "outgoing_invoice"

    return "unknown"