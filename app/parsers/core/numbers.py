# parsers/core/numbers.py

import re


# =========================
# NUMBER HELPERS
# =========================

def safe_float(v):
    """
    Безопасный float parser:
    1 234,50
    1234.50
    """
    if v in (None, ""):
        return None

    try:
        s = str(v).strip()

        # убираем пробелы-разделители тысяч
        s = s.replace(" ", "")

        # RU/UA decimal
        s = s.replace(",", ".")

        return float(s)

    except:
        return None


# =========================
# EXTRACT ALL NUMBERS
# =========================

def extract_numbers(values):
    nums = []

    for v in values:
        n = safe_float(v)

        if n is not None:
            nums.append(n)

    return nums


# =========================
# SIMPLE PRICE/TOTAL
# =========================

def extract_price_total(values):
    """
    Базовый fallback:
    последние 2 числа = price / total
    """

    nums = extract_numbers(values)

    if len(nums) < 2:
        return None, None

    price = nums[-2]
    total = nums[-1]

    # защита
    if price <= 0 or total <= 0:
        return None, None

    if total < price:
        return None, None

    return price, total


# =========================
# SIMPLE QTY
# =========================

# def extract_qty(values, price=None, total=None):
#     """
#     Базовый qty helper.

#     PRIORITY:
#     1. "10 шт"
#     2. total / price
#     3. fallback = 1
#     """

#     text = " ".join(map(str, values)).lower()

#     # =========================
#     # 1. EXPLICIT QTY
#     # =========================
#     m = re.search(
#         r"(\d+(?:[.,]\d+)?)\s*(шт|уп|ящ|бухта|м|кг|л)",
#         text
#     )

#     if m:
#         qty = safe_float(m.group(1))

#         if qty is not None and qty > 0:
#             return qty

#     # =========================
#     # 2. CALCULATED QTY
#     # =========================
#     if price and total and price > 0:
#         try:
#             qty = total / price

#             # защита от мусора
#             if 0 < qty <= 10000:
#                 return round(qty, 3)

#         except:
#             pass

#     # =========================
#     # 3. FALLBACK
#     # =========================
#     return 1.0