# app/apps/warehouse/services.py
"""
Приёмка товара по накладной поставщика. Три шага:

1. parse_document   — файл → строки накладной + сопоставление каждой строки с нашим вариантом.
                      Статус строки:
                        matched      — найдено точно (память сопоставлений, штрихкод, артикул);
                        needs_review — найден только похожий по названию товар (fuzzy) → нужна проверка;
                        new          — ничего не найдено, при проведении будет создан скрытый товар;
                        invalid      — нет названия/количества/цены, строка не приходуется.
2. set_line_variant — оператор подтверждает/исправляет сопоставление строки (или «создать новый»).
3. process_inventory_document — приход всех строк на склад (через stock.receive) одной транзакцией.
   Пока есть строки needs_review, проведение запрещено (если явно не accept_suggestions=True).
   Похожая уже проведённая накладная (duplicates.py) — тоже, пока оператор не подтвердит.
   Уже принятое сканером по этому документу не приходуется второй раз.
   Подтверждённые сопоставления запоминаются (VariantMatchMemory) — следующая накладная того же
   поставщика сопоставится автоматически.
4. reverse_inventory_document — отмена проведения (сторно): встречные движения, документ снова черновик.
"""

import hashlib
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.db.models import F, Max, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext as _
from rapidfuzz import fuzz, process

from app.apps.products.models import Product, ProductVariant
from app.apps.sellers.models import Seller
from app.apps.warehouse import duplicates, stock
from app.apps.warehouse.models import (
    InventoryDocument,
    InvoiceColumnProfile,
    ProductBarcode,
    StockMovement,
    Supplier,
    VariantMatchMemory,
    Warehouse,
)
from parsers.core.loader import NeedsAI, load_rows
from parsers.core.text_utils import code_key, fold_lookalikes
from parsers.detect import detect_supplier
from parsers.pipeline import header_signature
from parsers.pipeline import parse_rows as parse_invoice_rows

logger = logging.getLogger(__name__)

RETAIL_MARKUP = Decimal("1.40")
FUZZY_THRESHOLD = 80

MATCHED, NEEDS_REVIEW, NEW, INVALID = "matched", "needs_review", "new", "invalid"


class ReviewRequiredError(stock.StockError):
    code = "review_required"


class DuplicateDocumentError(stock.StockError):
    code = "duplicate_document"


class NeedsAIError(stock.StockError):
    code = "needs_ai"


def ai_enabled() -> bool:
    return settings.INVOICE_AI_MODE in ("manual", "auto") and bool(settings.ANTHROPIC_API_KEY)


def file_sha256(django_file) -> str:
    h = hashlib.sha256()
    for chunk in django_file.chunks():
        h.update(chunk)
    django_file.seek(0)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Сопоставление строки с вариантом
# ---------------------------------------------------------------------------


def _norm(value) -> str:
    return " ".join(str(value or "").split()).lower()


class VariantMatcher:
    """Индекс вариантов в памяти: точный поиск по коду/штрихкоду и fuzzy по названию."""

    def __init__(self, supplier=None):
        self.supplier = supplier
        rows = ProductVariant.objects.values_list("id", "variant_name", "code", "barcode")
        # ключи устойчивы к «двойникам»: латинская i в «Змiшувач», кириллическая «С» в артикуле «СN-20»
        self.by_code, self.by_barcode, self.names = {}, {}, {}
        for vid, name, code, barcode in rows:
            if code:
                self.by_code[code_key(code)] = vid
            if barcode:
                self.by_barcode[code_key(barcode)] = vid
            if name:
                self.names[vid] = fold_lookalikes(name)
        for vid, code in ProductBarcode.objects.values_list("variant_id", "code"):
            self.by_barcode.setdefault(code_key(code), vid)

    def _memory(self, sku, name):
        qs = VariantMatchMemory.objects.filter(supplier=self.supplier).order_by("-hit_count", "-last_used")
        if sku:
            hit = qs.filter(raw_code__iexact=sku).values_list("variant_id", flat=True).first()
            if hit:
                return hit
        if name:
            return qs.filter(raw_name__iexact=name).values_list("variant_id", flat=True).first()
        return None

    def match(self, item):
        """→ (status, variant_id, method, confidence, candidates)"""
        sku, barcode, name = _norm(item.get("sku")), _norm(item.get("barcode")), _norm(item.get("name"))

        vid = self._memory(sku, name)
        if vid:
            return MATCHED, vid, "memory", 1.0, []
        if barcode and code_key(barcode) in self.by_barcode:
            return MATCHED, self.by_barcode[code_key(barcode)], "barcode", 1.0, []
        if sku and code_key(sku) in self.by_code:
            return MATCHED, self.by_code[code_key(sku)], "sku", 0.95, []
        if name and self.names:
            found = process.extract(fold_lookalikes(name), self.names, scorer=fuzz.token_sort_ratio, limit=3)
            candidates = [
                {"variant_id": vid, "score": round(score)} for _, score, vid in found if score >= FUZZY_THRESHOLD
            ]
            if candidates:
                return NEEDS_REVIEW, candidates[0]["variant_id"], "fuzzy", candidates[0]["score"] / 100, candidates
        return NEW, None, None, 0.0, []


def _decimal(value, places):
    try:
        return Decimal(str(value)).quantize(Decimal(places), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return None


def _build_line(position, item, matcher):
    line = {
        "position": position,
        "name": item.get("name") or "",
        "sku": item.get("sku") or "",
        "barcode": item.get("barcode") or "",
        "unit": item.get("unit") or "",
        "currency": item.get("currency") or "UAH",
        "qty": None,
        "price": None,
        "status": INVALID,
        "variant_id": None,
        "method": None,
        "confidence": 0.0,
        "candidates": [],
        "error": None,
    }
    qty = _decimal(item.get("qty"), "0.001")
    price = _decimal(item.get("price") or 0, "0.0001")
    if not line["name"]:
        line["error"] = _("нет наименования")
    elif qty is None or qty <= 0:
        line["error"] = _("нет количества ({value!r})").format(value=item.get("qty"))
    elif price is None or price < 0:
        line["error"] = _("некорректная цена ({value!r})").format(value=item.get("price"))
    if line["error"]:
        return line

    line["qty"], line["price"] = str(qty), str(price)
    status, vid, method, confidence, candidates = matcher.match(item)
    line.update(status=status, variant_id=vid, method=method, confidence=confidence, candidates=candidates)
    return line


# ---------------------------------------------------------------------------
# Шаг 1. Разбор
# ---------------------------------------------------------------------------


@transaction.atomic
def parse_document(document: InventoryDocument) -> dict:
    document = InventoryDocument.objects.select_for_update().get(pk=document.pk)
    if document.processed:
        raise stock.StockError(_("Документ уже проведён"))

    try:
        rows = load_rows(document.file.path)
    except NeedsAI as exc:
        rows = []
        if not document.ai_result:
            raise NeedsAIError(_("Это скан или фото без текста: разберите накладную через ИИ")) from exc

    parsed = parse_invoice_rows(
        rows,
        columns=document.column_map,
        profiles=_column_profiles(document, rows),
        ai_result=document.ai_result,
    )
    if parsed.get("profile_id"):
        InvoiceColumnProfile.objects.filter(pk=parsed["profile_id"]).update(
            used_count=F("used_count") + 1, last_used_at=timezone.now()
        )
    meta = parsed.get("meta") or {}
    if meta.get("number") and not document.document_number:
        document.document_number = str(meta["number"])[:100]

    detected = parsed.get("detected_supplier")
    if document.supplier_id is None and detected and detected != "default":
        document.supplier = Supplier.objects.filter(code=detected, is_active=True).first()

    matcher = VariantMatcher(supplier=document.supplier)
    parsed["lines"] = [_build_line(i, item, matcher) for i, item in enumerate(parsed.get("items", []), start=1)]
    parsed["summary"] = {
        s: sum(1 for ln in parsed["lines"] if ln["status"] == s) for s in (MATCHED, NEEDS_REVIEW, NEW, INVALID)
    }
    document.extracted_data = parsed
    for field, value in duplicates.document_keys(document).items():
        setattr(document, field, value)
    document.save(
        update_fields=["extracted_data", "document_number", "supplier", "number_key", "fingerprint", "lines_total"]
    )
    return parsed


def _column_profiles(document, rows):
    """Сохранённые раскладки колонок поставщика (указанного или определённого по шапке)."""
    supplier = document.supplier
    if supplier is None and rows:
        code = detect_supplier(rows)
        if code != "default":
            supplier = Supplier.objects.filter(code=code, is_active=True).first()
    if supplier is None:
        return []
    return [{"id": p.pk, "header": p.header, "columns": p.columns} for p in supplier.column_profiles.all()[:50]]


COLUMN_ROLES = ("name", "qty", "price", "total", "sku", "barcode", "unit")


def set_document_columns(document, header_row, columns: dict, *, remember=False, user=None) -> InventoryDocument:
    """Колонки, указанные оператором для этой накладной (+ запомнить как профиль поставщика)."""
    if document.processed:
        raise stock.StockError(_("Документ уже проведён"))
    columns = {k: int(v) for k, v in columns.items() if k in COLUMN_ROLES and v is not None and str(v) != ""}
    missing = [k for k in ("name", "qty", "price") if k not in columns]
    if missing:
        raise stock.StockError(_("Укажите колонки: название, количество и цена"))
    if len(set(columns.values())) != len(columns):
        raise stock.StockError(_("Одна колонка выбрана для двух полей"))
    if remember:
        if document.supplier is None:
            raise stock.StockError(_("Чтобы запомнить колонки, укажите поставщика накладной"))
        signature = header_signature(load_rows(document.file.path), header_row, columns)
        if len(signature) < 2:
            raise stock.StockError(_("Укажите строку заголовков — по ней колонки узнаются в следующих накладных"))
        InvoiceColumnProfile.objects.create(
            supplier=document.supplier, header=signature, columns=columns, created_by=user
        )
    InventoryDocument.objects.filter(pk=document.pk).update(column_map={"header_row": header_row, "columns": columns})
    document.refresh_from_db()
    parse_document(document)
    return document


def request_ai_parse(document) -> InventoryDocument:
    """Поставить разбор накладной через ИИ в очередь (Celery)."""
    from app.core.tasks import QueueUnavailable, enqueue

    from .tasks import parse_document_ai_task

    if not ai_enabled():
        raise stock.StockError(_("Разбор через ИИ выключен в настройках"))
    if document.processed:
        raise stock.StockError(_("Документ уже проведён"))
    if document.ai_status in ("queued", "running"):
        raise stock.StockError(_("Разбор через ИИ уже выполняется"))
    InventoryDocument.objects.filter(pk=document.pk).update(ai_status="queued", ai_error="")
    try:
        enqueue(parse_document_ai_task, document.pk)
    except QueueUnavailable:
        InventoryDocument.objects.filter(pk=document.pk).update(ai_status="")
        raise stock.StockError(_("Фоновые задачи временно недоступны, попробуйте через минуту")) from None
    document.refresh_from_db()
    return document


def reset_document_columns(document) -> InventoryDocument:
    if document.processed:
        raise stock.StockError(_("Документ уже проведён"))
    InventoryDocument.objects.filter(pk=document.pk).update(column_map=None)
    document.refresh_from_db()
    parse_document(document)
    return document


# ---------------------------------------------------------------------------
# Шаг 2. Проверка оператором
# ---------------------------------------------------------------------------


@transaction.atomic
def set_line_variant(document: InventoryDocument, position: int, variant_id=None, create_new=False) -> dict:
    document = InventoryDocument.objects.select_for_update().get(pk=document.pk)
    if document.processed:
        raise stock.StockError(_("Документ уже проведён"))
    lines = (document.extracted_data or {}).get("lines") or []
    line = next((ln for ln in lines if ln["position"] == position), None)
    if line is None:
        raise stock.StockError(_("Строка {position} не найдена").format(position=position))
    if line["status"] == INVALID:
        raise stock.StockError(
            _("Строка {position} некорректна: {value}").format(position=position, value=line["error"])
        )

    if create_new:
        line.update(status=NEW, variant_id=None, method="manual", confidence=1.0)
    else:
        if not ProductVariant.objects.filter(pk=variant_id).exists():
            raise stock.StockError(_("Вариант {variant_id} не найден").format(variant_id=variant_id))
        line.update(status=MATCHED, variant_id=int(variant_id), method="manual", confidence=1.0)
    document.extracted_data["summary"] = {
        s: sum(1 for ln in lines if ln["status"] == s) for s in (MATCHED, NEEDS_REVIEW, NEW, INVALID)
    }
    document.save(update_fields=["extracted_data"])
    return line


# ---------------------------------------------------------------------------
# Шаг 3. Проведение
# ---------------------------------------------------------------------------


def _create_hidden_variant(document, line):
    product = Product.objects.create(name=line["name"], seller=document.seller)
    price = Decimal(line["price"])
    # код/штрихкод уникальны: если такой уже занят — сгенерируется свой
    code = line["sku"] if line["sku"] and not ProductVariant.objects.filter(code__iexact=line["sku"]).exists() else None
    barcode = (
        line["barcode"]
        if line["barcode"] and not ProductVariant.objects.filter(barcode=line["barcode"]).exists()
        else None
    )
    return ProductVariant.objects.create(
        product=product,
        variant_name=line["name"],
        code=code,
        barcode=barcode,
        cost_price=price,
        price=(price * RETAIL_MARKUP).quantize(Decimal("0.01")),
        available=False,  # скрыт из каталога до проверки карточки продавцом
    )


def _learn(supplier, line, variant_id):
    if not line["name"]:
        return
    memory = VariantMatchMemory.objects.filter(
        supplier=supplier,
        raw_code__iexact=line["sku"],
        raw_name__iexact=line["name"],
    ).first()
    if memory:
        memory.variant_id = variant_id
        memory.hit_count += 1
        memory.save(update_fields=["variant", "hit_count", "last_used"])
    else:
        VariantMatchMemory.objects.create(
            supplier=supplier,
            raw_code=line["sku"],
            raw_name=line["name"],
            variant_id=variant_id,
        )


def _lock_seller_and_document(document) -> InventoryDocument:
    """
    Накладные одного продавца проводятся и отменяются по очереди: две копии одной поставки,
    проводимые одновременно, иначе обе прошли бы проверку дублей. Порядок блокировок:
    продавец → документ → товары → остатки (как в stock.py).
    """
    Seller.objects.select_for_update().filter(pk=document.seller_id).first()
    return InventoryDocument.objects.select_for_update().get(pk=document.pk)


def _received_by_document(document) -> dict[int, Decimal]:
    """Сколько товара уже оприходовано по документу (сканером при приёмке) за вычетом сторно."""
    rows = (
        StockMovement.objects.filter(inventory_document=document)
        .values("variant_id")
        .annotate(
            got=Sum("quantity", filter=Q(movement_type=StockMovement.IN)),
            back=Sum("quantity", filter=Q(movement_type=StockMovement.IN_REVERSAL)),
        )
    )
    net = {r["variant_id"]: (r["got"] or Decimal("0")) - (r["back"] or Decimal("0")) for r in rows}
    return {vid: qty for vid, qty in net.items() if qty > 0}


def _variant_names(ids) -> dict[int, str]:
    return {
        v.pk: v.variant_name or (v.product.name if v.product_id else "") or f"#{v.pk}"
        for v in ProductVariant.objects.filter(pk__in=ids).select_related("product")
    }


@transaction.atomic
def process_inventory_document(
    document: InventoryDocument,
    warehouse: Warehouse,
    created_by,
    accept_suggestions=False,
    allow_duplicate=False,
) -> dict:
    """
    Проводит документ. Возвращает отчёт {"received": n, "created": n, "skipped": [...],
    "already_received": [...], "scanner_extra": [...], "duplicate_confirmed": {...}?}.
    """
    document = _lock_seller_and_document(document)
    if document.processed:
        raise stock.StockError(_("Документ уже проведён"))
    if warehouse.seller_id != document.seller_id:
        raise stock.StockError(_("Склад не принадлежит продавцу документа"))

    if not (document.extracted_data or {}).get("lines"):
        parse_document(document)
        document.refresh_from_db()
    data = document.extracted_data
    lines = data["lines"]

    review = [ln["position"] for ln in lines if ln["status"] == NEEDS_REVIEW]
    if review and not accept_suggestions:
        raise ReviewRequiredError(
            _("Нужно проверить сопоставление строк: {value}").format(value=", ".join(map(str, review))),
            positions=review,
        )

    report = {"received": 0, "created": 0, "skipped": [], "already_received": [], "scanner_extra": []}
    processed_twins = [d for d in duplicates.find_duplicates(document) if d["processed"]]
    if processed_twins and not allow_duplicate:
        raise DuplicateDocumentError(
            _("Похоже, эта накладная уже проведена (документ #{pk}). Если это другая поставка — подтвердите").format(
                pk=processed_twins[0]["id"]
            ),
            document_id=processed_twins[0]["id"],
        )
    if processed_twins:
        report["duplicate_confirmed"] = {
            "by": getattr(created_by, "email", "") or "",
            "documents": [d["id"] for d in processed_twins],
        }

    received = _received_by_document(document)  # принятое сканером не приходуем второй раз
    created = {}  # одинаковые новые позиции в одной накладной → один товар
    for line in lines:
        if line["status"] == INVALID:
            report["skipped"].append({"row": line["position"], "name": line["name"], "reason": line["error"]})
            continue
        if line["status"] == NEW:
            key = ("sku", _norm(line["sku"])) if line["sku"] else ("name", _norm(line["name"]))
            variant = created.get(key)
            if variant is None:
                variant = created[key] = _create_hidden_variant(document, line)
                report["created"] += 1
            line["variant_id"] = variant.pk
        else:
            variant = ProductVariant.objects.get(pk=line["variant_id"])
            price = Decimal(line["price"])
            if variant.cost_price != price:
                ProductVariant.objects.filter(pk=variant.pk).update(cost_price=price)

        if line["barcode"]:
            ProductBarcode.objects.get_or_create(code=line["barcode"], defaults={"variant": variant})
        _learn(document.supplier, line, variant.pk)

        qty = Decimal(line["qty"])
        already = min(received.get(variant.pk, Decimal("0")), qty)
        if already:
            received[variant.pk] -= already
            report["already_received"].append({"row": line["position"], "qty": str(already)})
        line["status"] = MATCHED
        if qty - already <= 0:
            continue
        stock.receive(
            variant,
            warehouse,
            qty - already,
            user=created_by,
            supplier=document.supplier,
            inventory_document=document,
            document_number=document.document_number,
            price_per_unit=Decimal(line["price"]),
            comment=f"Накладная, строка {line['position']} ({line['method'] or 'новый товар'})",
        )
        report["received"] += 1

    # отсканировано больше, чем есть в накладной (или товар, которого в ней нет) — показать оператору
    names = _variant_names([vid for vid, qty in received.items() if qty > 0])
    report["scanner_extra"] = [
        {"variant_id": vid, "name": names.get(vid, ""), "qty": str(qty)} for vid, qty in received.items() if qty > 0
    ]

    data["processing_report"] = report
    document.extracted_data = data
    document.processed = True
    document.processed_at = timezone.now()
    document.save(update_fields=["extracted_data", "processed", "processed_at"])
    return report


def _qty_text(value) -> str:
    return f"{Decimal(value).quantize(Decimal('0.001')):f}".rstrip("0").rstrip(".")


@transaction.atomic
def reverse_inventory_document(document: InventoryDocument, *, user, reason="") -> dict:
    """
    Отмена проведения (сторно): встречное движение «Сторно прихода» на всё, что документ оприходовал
    (строками и сканером). Журнал не правится — видны и приход, и отмена. Проданный или зарезервированный
    товар отменить нельзя. После отмены документ снова черновик: его можно исправить и провести.
    """
    document = _lock_seller_and_document(document)
    if not document.processed:
        raise stock.StockError(_("Документ не проведён"))
    rows = (
        StockMovement.objects.filter(inventory_document=document)
        .values("variant_id", "warehouse_id")
        .annotate(
            got=Sum("quantity", filter=Q(movement_type=StockMovement.IN)),
            back=Sum("quantity", filter=Q(movement_type=StockMovement.IN_REVERSAL)),
            price=Max("price_per_unit", filter=Q(movement_type=StockMovement.IN)),
        )
    )
    warehouses = Warehouse.objects.in_bulk({r["warehouse_id"] for r in rows})
    lines = [
        (r["variant_id"], warehouses[r["warehouse_id"]], net, r["price"])
        for r in rows
        if (net := (r["got"] or Decimal("0")) - (r["back"] or Decimal("0"))) > 0
    ]
    if not lines:
        raise stock.StockError(_("По документу нет оприходованного товара"))

    reason = str(reason or "").strip()[:500]
    try:
        stock.reverse_receipts(
            lines,
            user=user,
            supplier=document.supplier,
            inventory_document=document,
            document_number=document.document_number,
            comment=_("Сторно накладной #{pk}").format(pk=document.pk) + (f": {reason}" if reason else ""),
        )
    except stock.InsufficientStockError as exc:
        shortages = exc.context.get("shortages") or []
        names = _variant_names([s["variant_id"] for s in shortages])
        details = "; ".join(
            _("«{name}»: нужно {required}, свободно {available}").format(
                name=names.get(s["variant_id"], ""),
                required=_qty_text(s["required"]),
                available=_qty_text(s["available"]),
            )
            for s in shortages
        )
        raise stock.InsufficientStockError(
            _("Отменить проведение нельзя: часть товара уже продана или в резерве — {details}").format(details=details)
        ) from None

    data = document.extracted_data or {}
    reversal = {
        "at": timezone.now().isoformat(),
        "by": getattr(user, "email", "") or "",
        "reason": reason,
        "positions": len(lines),
        "report": data.pop("processing_report", None),
    }
    data.setdefault("reversals", []).append(reversal)
    document.extracted_data = data
    document.processed = False
    document.processed_at = None
    document.save(update_fields=["extracted_data", "processed", "processed_at"])
    return reversal


def suggest_variants(query, limit=10):
    """Поиск вариантов для ручного сопоставления строки (по названию, артикулу, штрихкоду)."""
    query = (query or "").strip()
    if not query:
        return ProductVariant.objects.none()
    return (
        ProductVariant.objects.filter(
            Q(variant_name__icontains=query)
            | Q(product__name__icontains=query)
            | Q(code__iexact=query)
            | Q(barcode__iexact=query)
        )
        .select_related("product")
        .order_by("variant_name")[:limit]
    )
