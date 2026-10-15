# parsers/core/numbers.py
import re

_SPACES = re.compile(r"[\s\u00a0\u202f\u2009']")
# Ячейка целиком — число (разделители, знак) и, возможно, валюта.
# Текст вроде «Труба 20мм» или «ABC-1» числом не считается.
_NUMERIC_CELL = re.compile(r"^-?[\d.,]*\d[\d.,]*(грн\.?|uah|usd|eur|₴|\$|€)?$", re.IGNORECASE)
_CURRENCY = re.compile(r"(грн\.?|uah|usd|eur|₴|\$|€)$", re.IGNORECASE)


def safe_float(v):
    """
    Число из ячейки накладной или None.

    Понимает форматы: 1234.5 · 1234,5 · 1 234,50 (в т.ч. неразрывный пробел) · 1.234,50 · 1,234.50 ·
    «12,5 грн» · «45.20 USD». Если в строке есть и точка, и запятая, десятичным считается
    последний разделитель. Одиночная запятая — десятичная (украинский/русский формат).
    """
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)

    s = _SPACES.sub("", str(v).strip())
    if not _NUMERIC_CELL.match(s):
        return None
    s = _CURRENCY.sub("", s)

    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif s.count(",") == 1:
        s = s.replace(",", ".")
    elif s.count(",") > 1 or s.count(".") > 1:
        # 1,234,567 / 1.234.567 — разделители тысяч
        s = s.replace(",", "").replace(".", "")

    try:
        return float(s)
    except ValueError:
        return None


def extract_numbers(values):
    nums = []
    for v in values:
        n = safe_float(v)
        if n is not None:
            nums.append(n)
    return nums


def extract_price_total(values):
    """Запасной вариант: два последних числа строки = цена и сумма."""
    nums = extract_numbers(values)
    if len(nums) < 2:
        return None, None
    price, total = nums[-2], nums[-1]
    if price <= 0 or total <= 0 or total < price:
        return None, None
    return price, total
