"""
Разбор накладной через Claude (запасной вариант): сканы, фото, PDF и таблицы, которые не разобрались иначе.

Используется только если включено настройкой (INVOICE_AI_MODE) и задан ключ API. Ответ модели —
строго по схеме (инструмент record_invoice), результат проходит ту же проверку арифметики, что и остальные.
"""

import base64
import os

from parsers.core.loader import IMAGE_EXTENSIONS
from parsers.core.text_utils import normalize_text
from parsers.normalizer import normalize_item

MAX_PDF_BYTES = 20 * 1024 * 1024
MAX_IMAGE_BYTES = 5 * 1024 * 1024
MAX_ROWS, MAX_COLS, MAX_CELL = 400, 40, 150
MEDIA_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}


class AIError(Exception):
    pass


SYSTEM_PROMPT = """You extract goods lines from Ukrainian supplier invoices (видаткова накладна, рахунок, \
расходная накладная) for a plumbing shop's warehouse receiving. Documents are often made by hand, columns \
may be mislabeled, missing or shifted, Latin letters may replace Cyrillic ones.

Rules:
- Record every goods line exactly once, in document order. Skip subtotals, totals, VAT lines, discounts \
summary, signatures, notes, bank details.
- name: exactly as written (do not translate, do not fix spelling). sku: supplier article/code if present \
(not the row number). barcode: EAN/UPC digits if present.
- qty: quantity in the document's unit; unit: шт, м, кг, компл… as written.
- price: price per unit actually charged. If both prices without VAT and with VAT exist, use the price WITH \
VAT (the buyer is not a VAT payer). total: line amount for that price. Check qty × price ≈ total.
- Numbers: plain numbers with a dot decimal separator (1 234,50 → 1234.5).
- document_date: YYYY-MM-DD. total: the final amount to pay. If something is unreadable, say so in notes \
instead of guessing."""

SCHEMA = {
    "type": "object",
    "properties": {
        "document_number": {"type": ["string", "null"]},
        "document_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
        "supplier_name": {"type": ["string", "null"]},
        "currency": {"type": ["string", "null"], "description": "UAH, USD, EUR"},
        "total": {"type": ["number", "null"]},
        "vat": {"type": ["number", "null"]},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "sku": {"type": ["string", "null"]},
                    "barcode": {"type": ["string", "null"]},
                    "qty": {"type": "number"},
                    "unit": {"type": ["string", "null"]},
                    "price": {"type": "number"},
                    "total": {"type": ["number", "null"]},
                },
                "required": ["name", "qty", "price"],
            },
        },
        "notes": {"type": ["string", "null"], "description": "Problems: unreadable or ambiguous parts"},
    },
    "required": ["items"],
}


def rows_to_text(rows) -> str:
    """Таблица → компактный TSV: без пустых строк и колонок, длинные ячейки обрезаны."""
    rows = [[normalize_text(c)[:MAX_CELL] if c not in (None, "") else "" for c in r] for r in rows if r]
    rows = [r for r in rows if any(r)][:MAX_ROWS]
    used = sorted({i for r in rows for i, c in enumerate(r) if c})[:MAX_COLS]
    return "\n".join("\t".join(r[i] if i < len(r) else "" for i in used) for r in rows)


def build_content(file_path: str, rows=None) -> list:
    ext = os.path.splitext(file_path)[1].lower()
    instruction = {"type": "text", "text": "Extract the invoice and call record_invoice."}
    if rows:
        text = rows_to_text(rows)
        return [
            {"type": "text", "text": f"Invoice exported from a spreadsheet (tab-separated cells):\n\n{text}"},
            instruction,
        ]
    size = os.path.getsize(file_path)
    with open(file_path, "rb") as fh:
        data = base64.standard_b64encode(fh.read()).decode()
    if ext == ".pdf":
        if size > MAX_PDF_BYTES:
            raise AIError("PDF больше 20 МБ")
        return [
            {"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}},
            instruction,
        ]
    if ext in IMAGE_EXTENSIONS:
        if size > MAX_IMAGE_BYTES:
            raise AIError("Фото больше 5 МБ — уменьшите разрешение")
        return [
            {"type": "image", "source": {"type": "base64", "media_type": MEDIA_TYPES[ext], "data": data}},
            instruction,
        ]
    raise AIError(f"Формат {ext} не поддерживается для разбора через ИИ")


def call_claude(content: list, *, api_key: str, model: str) -> tuple[dict, dict]:
    """→ (данные по схеме, {"input_tokens", "output_tokens"}). Потоковый запрос: длинные накладные дают большой ответ."""
    import anthropic

    client = anthropic.Anthropic(api_key=api_key, timeout=300, max_retries=2)
    try:
        with client.messages.stream(
            model=model,
            max_tokens=32000,
            system=SYSTEM_PROMPT,
            tools=[{"name": "record_invoice", "description": "Record the extracted invoice", "input_schema": SCHEMA}],
            tool_choice={"type": "tool", "name": "record_invoice"},
            messages=[{"role": "user", "content": content}],
        ) as stream:
            message = stream.get_final_message()
    except anthropic.APIStatusError as exc:
        raise AIError(f"Claude API: {exc.status_code}") from exc
    except anthropic.APIError as exc:
        raise AIError(f"Claude API: {exc.__class__.__name__}") from exc
    if message.stop_reason == "max_tokens":
        raise AIError("Накладная слишком большая для одного запроса")
    data = next((b.input for b in message.content if b.type == "tool_use"), None)
    if not isinstance(data, dict):
        raise AIError("Модель не вернула данные накладной")
    return data, {"input_tokens": message.usage.input_tokens, "output_tokens": message.usage.output_tokens}


def to_result(data: dict) -> dict:
    """Ответ модели → формат разбора (items/meta/totals), как у остальных парсеров."""
    items = []
    for i, item in enumerate(data.get("items") or [], start=1):
        qty, price = item.get("qty"), item.get("price")
        items.append(
            normalize_item(
                {
                    "position": i,
                    "sku": item.get("sku") or "",
                    "barcode": item.get("barcode") or "",
                    "name": item.get("name") or "",
                    "qty": qty,
                    "unit": item.get("unit") or "",
                    "price": price,
                    "total": item.get("total") if item.get("total") is not None else (qty or 0) * (price or 0),
                    "currency": (data.get("currency") or "").upper() or None,
                }
            )
        )
    return {
        "items": items,
        "meta": {
            "number": data.get("document_number"),
            "date": data.get("document_date"),
            "supplier": data.get("supplier_name"),
        },
        "totals": {"total": data.get("total"), "vat": data.get("vat")},
        "notes": data.get("notes"),
    }


def extract(file_path: str, *, api_key: str, model: str, rows=None) -> dict:
    if not api_key:
        raise AIError("Не задан ключ ANTHROPIC_API_KEY")
    data, usage = call_claude(build_content(file_path, rows), api_key=api_key, model=model)
    return {**to_result(data), "model": model, "usage": usage}
