"""
Проверка качества разбора накладной — не доверяем ни заголовкам, ни парсеру, а сверяем арифметику:
  • в каждой строке количество × цена = сумма (с допуском на округление до копеек);
  • сумма строк = итог документа (или итог без ПДВ / с ПДВ).
"""

from parsers.core.numbers import safe_float


def _num(value):
    n = safe_float(value)
    return n if n is not None and n > 0 else None


def line_consistent(qty, price, total) -> bool:
    if not (qty and price and total):
        return False
    # цена округлена до копеек: погрешность растёт с количеством
    tolerance = max(0.02, total * 0.005) + 0.01 * qty
    return abs(qty * price - total) <= tolerance


def assess(items: list, totals: dict | None = None) -> dict:
    totals = totals or {}
    lines = len(items)
    consistent, bad_positions, missing = 0, [], 0
    sum_items = 0.0
    for i, item in enumerate(items, start=1):
        qty, price, total = _num(item.get("qty")), _num(item.get("price")), _num(item.get("total"))
        if not (item.get("name") and qty and price):
            missing += 1
        if line_consistent(qty, price, total):
            consistent += 1
        else:
            bad_positions.append(item.get("position") or i)
        sum_items += total or (qty or 0) * (price or 0)

    doc_total, vat = _num(totals.get("total")), _num(totals.get("vat"))
    sum_match = None
    if doc_total and lines:
        tolerance = max(0.05, doc_total * 0.002)
        sum_match = any(abs(sum_items - t) <= tolerance for t in (doc_total, doc_total - (vat or 0), doc_total / 1.2))
        sum_match = sum_match or (vat is not None and abs(sum_items + vat - doc_total) <= tolerance)

    if not lines:
        verdict, score = "empty", 0.0
    else:
        share = consistent / lines
        score = round(
            0.7 * share + 0.3 * (1.0 if sum_match else 0.5 if sum_match is None else 0.0) - 0.2 * missing / lines, 3
        )
        if share == 1 and sum_match is not False and not missing:
            verdict = "ok"
        elif share >= 0.8 and not missing:
            verdict = "warning"
        else:
            verdict = "bad"
    return {
        "verdict": verdict,
        "score": score,
        "lines": lines,
        "consistent": consistent,
        "inconsistent_positions": bad_positions[:50],
        "missing": missing,
        "sum_items": round(sum_items, 2),
        "doc_total": doc_total,
        "sum_match": sum_match,
    }
