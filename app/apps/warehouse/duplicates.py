"""
Поиск дублей накладной: та же поставка, загруженная ещё раз (пересохранённый файл, фото вместо Excel,
выбран другой поставщик, номер записан иначе). SHA-256 файла ловит только байт-в-байт тот же файл,
поэтому сравниваются данные:

- номер     — «№ 00123», «123», «ВН-0123» дают один ключ; поставщик тот же или у одной из накладных
              не указан; за последний год (у многих поставщиков нумерация начинается заново с января);
- строки    — тот же набор «название + количество + цена» (номер мог не распознаться);
- похожие   — та же сумма строк и ≥ 80 % одинаковых строк (из трёх и больше), например одну строку
              распознало иначе.

Совпадение не запрещает проведение навсегда: такие же поставки бывают каждый месяц, поэтому оператор
видит, с чем совпало, и может подтвердить «это другая накладная».
"""

import hashlib
import json
import re
from collections import Counter
from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.utils import timezone

from parsers.core.text_utils import code_key, fold_lookalikes

NUMBER_WINDOW = timedelta(days=365)
CONTENT_WINDOW = timedelta(days=120)
SIMILAR_SHARE = 0.8
SIMILAR_MIN_LINES = 3


def number_key(value) -> str:
    """Ключ номера документа: без «№», пробелов и разделителей, двойники букв сведены, без ведущих нулей."""
    key = re.sub(r"[^0-9A-ZА-ЯІЇЄҐ]", "", code_key(value))
    key = re.sub(r"^NO?(?=\d)", "", key)  # «No 123», «N123»
    return re.sub(r"(?<!\d)0+(?=\d)", "", key)


def _name_key(name) -> str:
    return re.sub(r"[\W_]+", "", fold_lookalikes(name))


def _decimal(value, places):
    try:
        return Decimal(str(value)).quantize(Decimal(places))
    except (InvalidOperation, TypeError, ValueError):
        return None


def line_keys(lines) -> list[tuple[str, str, str]]:
    """Строки накладной → [(название, кол-во, цена)] для сравнения (некорректные строки не участвуют)."""
    keys = []
    for line in lines or []:
        qty, price = _decimal(line.get("qty"), "0.001"), _decimal(line.get("price"), "0.01")
        name = _name_key(line.get("name"))
        if line.get("status") != "invalid" and name and qty and price is not None:
            keys.append((name, str(qty), str(price)))
    return keys


def fingerprint(keys) -> str:
    return hashlib.sha256(json.dumps(sorted(keys), ensure_ascii=False).encode()).hexdigest() if keys else ""


def lines_total(keys) -> Decimal | None:
    if not keys:
        return None
    return sum((Decimal(q) * Decimal(p) for _, q, p in keys), Decimal("0")).quantize(Decimal("0.01"))


def document_keys(document) -> dict:
    """Поля InventoryDocument для поиска дублей — по номеру и распознанным строкам."""
    keys = line_keys((document.extracted_data or {}).get("lines"))
    return {
        "number_key": number_key(document.document_number),
        "fingerprint": fingerprint(keys),
        "lines_total": lines_total(keys),
    }


def find_duplicates(document) -> list[dict]:
    """Другие накладные продавца, похожие на эту поставку: сначала проведённые, затем новые."""
    from .models import InventoryDocument

    keys = line_keys((document.extracted_data or {}).get("lines"))
    own_number = number_key(document.document_number)
    own_print, own_total = fingerprint(keys), lines_total(keys)
    now = timezone.now()

    others = (
        InventoryDocument.objects.filter(seller_id=document.seller_id)
        .exclude(pk=document.pk)
        .select_related("supplier")
    )
    candidates = {}
    if own_number:
        for doc in others.filter(number_key=own_number, uploaded_at__gte=now - NUMBER_WINDOW):
            if not (document.supplier_id and doc.supplier_id and document.supplier_id != doc.supplier_id):
                candidates.setdefault(doc.pk, (doc, set()))[1].add("number")
    recent = others.filter(uploaded_at__gte=now - CONTENT_WINDOW)
    if own_print:
        for doc in recent.filter(fingerprint=own_print):
            candidates.setdefault(doc.pk, (doc, set()))[1].add("content")
    if own_total is not None and len(keys) >= SIMILAR_MIN_LINES:
        for doc in recent.filter(lines_total=own_total).exclude(pk__in=candidates):
            same = _same_lines(keys, line_keys((doc.extracted_data or {}).get("lines")))
            if same >= SIMILAR_SHARE * len(keys):
                candidates.setdefault(doc.pk, (doc, set()))[1].add("similar")

    result = []
    for doc, reasons in candidates.values():
        other_keys = line_keys((doc.extracted_data or {}).get("lines"))
        result.append(
            {
                "id": doc.pk,
                "document_number": doc.document_number,
                "supplier_name": doc.supplier.name if doc.supplier_id else None,
                "uploaded_at": doc.uploaded_at.isoformat(),
                "processed": doc.processed,
                "processed_at": doc.processed_at.isoformat() if doc.processed_at else None,
                "reasons": sorted(reasons),
                "same_lines": _same_lines(keys, other_keys),
                "lines": len(other_keys),
            }
        )
    return sorted(result, key=lambda d: (not d["processed"], d["id"]))


def _same_lines(a, b) -> int:
    return sum((Counter(a) & Counter(b)).values())
