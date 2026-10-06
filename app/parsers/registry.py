# parsers/registry.py
from typing import Dict, Callable, List, Any
from parsers.detect import detect_supplier
from parsers.context import ParseContext
from .suppliers.aquadom import AquadomParser
from .suppliers.presto import PrestoPSParser
from .suppliers.santan import SantanParser


from .suppliers.ber import BerParser
from .suppliers.default import DefaultParser
from .normalizer import normalize_item


# Реестр парсеров
PARSERS: Dict[str, Callable] = {
    "aquadom": AquadomParser,
    "presto": PrestoPSParser,
    "santan": SantanParser,  # Регистрируем
    "default": DefaultParser,
    # "ber": BerParser,

}

def get_parser(supplier_code: str):
    """Возвращает класс парсера по коду поставщика"""
    parser_class = PARSERS.get(supplier_code, PARSERS["default"])
    return parser_class()


def parse(rows):
    supplier_code = detect_supplier(rows)
    parser = get_parser(supplier_code)
    
    context = ParseContext(supplier_code=supplier_code)

    result = parser.parse(rows, context)

    # 🔥 нормализация items
    result["items"] = [normalize_item(i) for i in result.get("items", [])]

    result["confidence"] = 0.9 if result.get("items") else 0.3
    result["detected_supplier"] = supplier_code

    return result




