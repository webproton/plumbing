"""
Полный разбор накладной (то, что использует склад):

1. Колонки, заданные оператором для ЭТОЙ накладной, — приоритет над всем.
2. Основной парсер (поставщики + TableEngine) — как и раньше.
3. Проверка арифметики (quality.assess). Сошлось — результат основного парсера, ничего не меняется.
4. Не сошлось — пробуем сохранённые профили колонок поставщика (если шапка совпала)
   и универсальный разбор по содержимому; берём вариант с лучшей проверкой.
"""

import logging

from parsers import universal
from parsers.core.text_utils import fold_lookalikes
from parsers.detect import detect_supplier
from parsers.normalizer import normalize_item
from parsers.quality import assess
from parsers.registry import parse as classic_parse
from parsers.utils import normalize_output

logger = logging.getLogger(__name__)

MIN_GAIN = 0.05  # альтернатива должна быть заметно лучше основного парсера


def header_signature(rows, header_row, columns) -> dict:
    """Тексты заголовков выбранных колонок: по ним профиль узнаёт «свою» шапку в следующих накладных."""
    if header_row is None or header_row >= len(rows):
        return {}
    row = rows[header_row]
    signature = {}
    for col in columns.values():
        if col < len(row) and row[col] not in (None, ""):
            signature[str(col)] = fold_lookalikes(str(row[col]))
    return signature


def _profile_start(rows, profile) -> int | None:
    signature = profile.get("header") or {}
    if len(signature) < 2:
        return None
    for idx, row in enumerate(rows[:80]):
        same = sum(
            1
            for col, text in signature.items()
            if int(col) < len(row) and fold_lookalikes(str(row[int(col)] or "")) == text
        )
        if same >= max(2, round(len(signature) * 0.67)):
            return idx + 1
    return None


def _candidate(engine, rows, columns, start, totals, extra=None):
    items = _strip_positions([normalize_item(i) for i in universal.extract_items(rows, columns, start)])
    return {"engine": engine, "items": items, "quality": assess(items, totals), "columns": columns, **(extra or {})}


def parse_rows(rows: list, *, columns: dict | None = None, profiles=(), ai_result: dict | None = None) -> dict:
    """
    columns   — {"header_row": i | None, "columns": {"name": i, "qty": i, "price": i, "total"?: i, ...}} от оператора;
    profiles  — [{"id": …, "header": {"кол": "текст заголовка"}, "columns": {...}}] сохранённые для поставщика;
    ai_result — готовый разбор через ИИ (parsers.ai.extract), участвует в сравнении наравне с остальными.
    """
    try:
        result = classic_parse(rows)
        result["engine"] = "parser"
    except Exception as exc:  # noqa: BLE001 — основной парсер упал: пробуем остальные способы
        logger.warning("Основной парсер накладной упал: %s", exc)
        result = normalize_output({"items": [], "meta": {}, "totals": {}})
        result.update(detected_supplier=detect_supplier(rows), engine="parser", parser_error=str(exc))
    totals = result.get("totals") or {}
    _strip_positions(result["items"])
    result["quality"] = assess(result["items"], totals)

    if columns and columns.get("columns"):
        header_row = columns.get("header_row")
        start = header_row + 1 if header_row is not None else 0
        chosen = _candidate("manual", rows, columns["columns"], start, totals, {"header_row": header_row})
        return _apply(result, chosen)

    if result["quality"]["verdict"] == "ok" and not ai_result:
        return result

    candidates = []
    if ai_result and ai_result.get("items"):
        ai_totals = ai_result.get("totals") or {}
        candidates.append(
            {
                "engine": "ai",
                "items": ai_result["items"],
                "quality": assess(ai_result["items"], ai_totals if ai_totals.get("total") else totals),
                "columns": None,
                "meta": ai_result.get("meta") or {},
            }
        )
    for profile in profiles:
        start = _profile_start(rows, profile)
        if start is not None:
            candidates.append(
                _candidate("profile", rows, profile["columns"], start, totals, {"profile_id": profile.get("id")})
            )
    found = universal.detect_columns(rows)
    if found:
        start = found["header_row"] + 1 if found["header_row"] is not None else found["first_row"]
        candidates.append(
            _candidate("universal", rows, found["columns"], start, totals, {"header_row": found["header_row"]})
        )

    candidates = [c for c in candidates if c["items"]]
    if candidates:
        # при равной проверке ИИ (его запросили явно или автоматически из-за плохого разбора) приоритетнее
        best = max(candidates, key=lambda c: (c["quality"]["score"], c["engine"] == "ai"))
        gain = 0 if best["engine"] == "ai" and result["quality"]["verdict"] != "ok" else MIN_GAIN
        if best["quality"]["score"] >= result["quality"]["score"] + gain:
            return _apply(result, best)
    return result


def _strip_positions(items):
    """«1 Змішувач», «2 Сифон»… — номер позиции склеился с названием (PDF, объединённые ячейки)."""
    if len(items) >= 2 and all(str(it.get("name") or "").startswith(f"{i} ") for i, it in enumerate(items, start=1)):
        for i, it in enumerate(items, start=1):
            it["name"] = it["name"][len(f"{i} ") :].strip()
    return items


def _apply(result, chosen):
    result["parser_items"] = len(result.get("items") or [])
    result["parser_quality"] = result["quality"]
    result["items"] = chosen["items"]
    result["quality"] = chosen["quality"]
    result["engine"] = chosen["engine"]
    result["columns"] = (
        {"header_row": chosen.get("header_row"), "columns": chosen["columns"]} if chosen["columns"] else None
    )
    meta = result.setdefault("meta", {})
    for key, value in (chosen.get("meta") or {}).items():
        if value and not meta.get(key):
            meta[key] = value
    if chosen.get("profile_id"):
        result["profile_id"] = chosen["profile_id"]
    return result
