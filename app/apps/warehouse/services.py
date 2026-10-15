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
   Подтверждённые сопоставления запоминаются (VariantMatchMemory) — следующая накладная того же
   поставщика сопоставится автоматически.
"""
import hashlib
import logging
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rapidfuzz import fuzz, process

from parsers.core.loader import load_rows
from parsers.registry import parse as run_invoice_parser

from app.apps.products.models import Product, ProductVariant
from app.apps.warehouse import stock
from app.apps.warehouse.models import (
    InventoryDocument, ProductBarcode, Supplier, VariantMatchMemory, Warehouse,
)

logger = logging.getLogger(__name__)

RETAIL_MARKUP = Decimal("1.40")
FUZZY_THRESHOLD = 80

MATCHED, NEEDS_REVIEW, NEW, INVALID = "matched", "needs_review", "new", "invalid"


class ReviewRequiredError(stock.StockError):
    code = "review_required"


class DuplicateDocumentError(stock.StockError):
    code = "duplicate_document"


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
        self.by_code, self.by_barcode, self.names = {}, {}, {}
        for vid, name, code, barcode in rows:
            if code:
                self.by_code[_norm(code)] = vid
            if barcode:
                self.by_barcode[_norm(barcode)] = vid
            if name:
                self.names[vid] = _norm(name)
        for vid, code in ProductBarcode.objects.values_list("variant_id", "code"):
            self.by_barcode.setdefault(_norm(code), vid)

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
        if barcode and barcode in self.by_barcode:
            return MATCHED, self.by_barcode[barcode], "barcode", 1.0, []
        if sku and sku in self.by_code:
            return MATCHED, self.by_code[sku], "sku", 0.95, []
        if name and self.names:
            found = process.extract(name, self.names, scorer=fuzz.token_sort_ratio, limit=3)
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
        "qty": None, "price": None,
        "status": INVALID, "variant_id": None, "method": None, "confidence": 0.0,
        "candidates": [], "error": None,
    }
    qty = _decimal(item.get("qty"), "0.001")
    price = _decimal(item.get("price") or 0, "0.0001")
    if not line["name"]:
        line["error"] = "нет наименования"
    elif qty is None or qty <= 0:
        line["error"] = f"нет количества ({item.get('qty')!r})"
    elif price is None or price < 0:
        line["error"] = f"некорректная цена ({item.get('price')!r})"
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
        raise stock.StockError("Документ уже проведён")

    parsed = run_invoice_parser(load_rows(document.file.path))
    meta = parsed.get("meta") or {}
    if meta.get("number") and not document.document_number:
        document.document_number = str(meta["number"])[:100]

    detected = parsed.get("detected_supplier")
    if document.supplier_id is None and detected and detected != "default":
        document.supplier = Supplier.objects.filter(code=detected, is_active=True).first()

    matcher = VariantMatcher(supplier=document.supplier)
    parsed["lines"] = [_build_line(i, item, matcher) for i, item in enumerate(parsed.get("items", []), start=1)]
    parsed["summary"] = {s: sum(1 for ln in parsed["lines"] if ln["status"] == s)
                         for s in (MATCHED, NEEDS_REVIEW, NEW, INVALID)}
    document.extracted_data = parsed
    document.save(update_fields=["extracted_data", "document_number", "supplier"])
    return parsed


# ---------------------------------------------------------------------------
# Шаг 2. Проверка оператором
# ---------------------------------------------------------------------------

@transaction.atomic
def set_line_variant(document: InventoryDocument, position: int, variant_id=None, create_new=False) -> dict:
    document = InventoryDocument.objects.select_for_update().get(pk=document.pk)
    if document.processed:
        raise stock.StockError("Документ уже проведён")
    lines = (document.extracted_data or {}).get("lines") or []
    line = next((ln for ln in lines if ln["position"] == position), None)
    if line is None:
        raise stock.StockError(f"Строка {position} не найдена")
    if line["status"] == INVALID:
        raise stock.StockError(f"Строка {position} некорректна: {line['error']}")

    if create_new:
        line.update(status=NEW, variant_id=None, method="manual", confidence=1.0)
    else:
        if not ProductVariant.objects.filter(pk=variant_id).exists():
            raise stock.StockError(f"Вариант {variant_id} не найден")
        line.update(status=MATCHED, variant_id=int(variant_id), method="manual", confidence=1.0)
    document.extracted_data["summary"] = {s: sum(1 for ln in lines if ln["status"] == s)
                                          for s in (MATCHED, NEEDS_REVIEW, NEW, INVALID)}
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
    barcode = line["barcode"] if line["barcode"] and not ProductVariant.objects.filter(
        barcode=line["barcode"]).exists() else None
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
        supplier=supplier, raw_code__iexact=line["sku"], raw_name__iexact=line["name"],
    ).first()
    if memory:
        memory.variant_id = variant_id
        memory.hit_count += 1
        memory.save(update_fields=["variant", "hit_count", "last_used"])
    else:
        VariantMatchMemory.objects.create(
            supplier=supplier, raw_code=line["sku"], raw_name=line["name"], variant_id=variant_id,
        )


@transaction.atomic
def process_inventory_document(document: InventoryDocument, warehouse: Warehouse, created_by,
                               accept_suggestions=False, allow_duplicate_number=False) -> dict:
    """Проводит документ. Возвращает отчёт {"received": n, "created": n, "skipped": [...]}."""
    document = InventoryDocument.objects.select_for_update().get(pk=document.pk)
    if document.processed:
        raise stock.StockError("Документ уже проведён")
    if warehouse.seller_id != document.seller_id:
        raise stock.StockError("Склад не принадлежит продавцу документа")

    if not (document.extracted_data or {}).get("lines"):
        parse_document(document)
        document.refresh_from_db()
    data = document.extracted_data
    lines = data["lines"]

    review = [ln["position"] for ln in lines if ln["status"] == NEEDS_REVIEW]
    if review and not accept_suggestions:
        raise ReviewRequiredError(
            f"Нужно проверить сопоставление строк: {', '.join(map(str, review))}", positions=review,
        )

    if document.document_number and not allow_duplicate_number:
        dup = InventoryDocument.objects.filter(
            seller_id=document.seller_id, supplier_id=document.supplier_id,
            document_number=document.document_number, processed=True,
        ).exclude(pk=document.pk).first()
        if dup:
            raise DuplicateDocumentError(
                f"Накладная №{document.document_number} этого поставщика уже проведена (документ #{dup.pk})",
                document_id=dup.pk,
            )

    report = {"received": 0, "created": 0, "skipped": []}
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

        stock.receive(
            variant, warehouse, line["qty"],
            user=created_by,
            supplier=document.supplier,
            inventory_document=document,
            document_number=document.document_number,
            price_per_unit=Decimal(line["price"]),
            comment=f"Накладная, строка {line['position']} ({line['method'] or 'новый товар'})",
        )
        line["status"] = MATCHED
        report["received"] += 1

    data["processing_report"] = report
    document.extracted_data = data
    document.processed = True
    document.processed_at = timezone.now()
    document.save(update_fields=["extracted_data", "processed", "processed_at"])
    return report


def suggest_variants(query, limit=10):
    """Поиск вариантов для ручного сопоставления строки (по названию, артикулу, штрихкоду)."""
    query = (query or "").strip()
    if not query:
        return ProductVariant.objects.none()
    return (
        ProductVariant.objects.filter(
            Q(variant_name__icontains=query) | Q(product__name__icontains=query)
            | Q(code__iexact=query) | Q(barcode__iexact=query)
        )
        .select_related("product")
        .order_by("variant_name")[:limit]
    )
