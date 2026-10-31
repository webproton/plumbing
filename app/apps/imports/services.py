"""
Синхронизация каталогов поставщиков.

sync_source:   скачать каталог → обновить SupplierItem → связать новые позиции с нашими вариантами
               (по штрихкоду/артикулу) → обновить цены и видимость связанных вариантов.
link_items / publish_items / ignore_items — ручные действия продавца над позициями поставщика.

Остатки поставщика НЕ попадают в наш склад: склад меняется только движениями (приход, инвентаризация).
Позиции поставщика влияют на цену и (опционально) на видимость товара в каталоге.
"""

import logging
from dataclasses import asdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from app.apps.products.catalog.services import CategoryResolver
from app.apps.products.models import Brand, Category, Product, ProductVariant
from app.apps.products.services import discount_fields, editable_variants
from app.apps.warehouse.models import CurrencyRate, ProductBarcode
from app.core.http import FetchError

from .connectors import ConnectorError, get_connector
from .formats import FormatError, SourceItem
from .models import ImportRun, ImportSource, SupplierItem

logger = logging.getLogger(__name__)

BATCH = 500
CENT = Decimal("0.01")
UNKNOWN_QTY = Decimal("999")  # у поставщика «есть», а сколько — фид не говорит
ITEM_FIELDS = [
    "sku",
    "barcode",
    "name",
    "brand",
    "category_name",
    "description",
    "url",
    "price",
    "old_price",
    "cost",
    "currency",
    "cost_currency",
    "quantity",
    "available",
    "photos",
    "params",
]


# у модели размеры по умолчанию 10 (наследие мебели) — у товаров поставщика их нет, не показываем выдуманные
NO_DIMENSIONS = dict.fromkeys(
    ("dimensions_width", "dimensions_height", "dimensions_depth", "dimensions_weight", "dimensions_thickness"), None
)


class ImportActionError(Exception):
    """Ошибка действия импорта, понятная пользователю."""


# ---------------------------------------------------------------------------
# Права: какие варианты продавец может менять импортом
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Цены
# ---------------------------------------------------------------------------


class Pricing:
    def __init__(self, source: ImportSource):
        self.source = source
        self.rates = {r.code.upper(): r.rate for r in CurrencyRate.objects.all()}
        for own in ((source.options or {}).get("feed_rates") or {}, source.currency_rates or {}):
            self.rates.update({code.upper(): Decimal(str(rate)) for code, rate in own.items() if rate})
        self.rates["UAH"] = Decimal(1)

    def rate(self, currency: str) -> Decimal | None:
        code = (currency or self.source.currency or "UAH").upper()
        return self.rates.get("UAH" if code in ("UAH", "ГРН", "RUR_UAH") else code)

    def _round(self, value: Decimal) -> Decimal:
        step = self.source.price_rounding if self.source.price_rounding and self.source.price_rounding > 0 else CENT
        return ((value / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step).quantize(CENT)

    def cost(self, item) -> Decimal | None:
        """Закупка в гривнах. Своя валюта закупки (опт в $ при РРЦ в грн), иначе — валюта прайса;
        закупка, посчитанная из РРЦ минус скидка партнёра, — в валюте РРЦ."""
        cost = self.source.item_cost(item)
        own = getattr(item, "cost_currency", "") if item.cost else ""
        rate = self.rate(own or item.currency)
        return (cost * rate).quantize(Decimal("0.0001")) if cost and rate else None

    def sale(self, item) -> Decimal | None:
        rate = self.rate(item.currency)
        price = item.price * rate if item.price and rate else None
        markup = Decimal(1) + self.source.markup_percent / Decimal(100)
        cost = self.cost(item)
        if self.source.price_mode == ImportSource.PRICE_MARKUP:
            base = cost * markup if cost else price
        else:
            base = price or (cost * markup if cost else None)
        if not base or base <= 0:
            return None
        return self._round(base)

    def old(self, item, sale: Decimal) -> Decimal | None:
        rate = self.rate(item.currency)
        if not item.old_price or not rate:
            return None
        old = self._round(item.old_price * rate)
        return old if old > sale else None


# ---------------------------------------------------------------------------
# Синхронизация
# ---------------------------------------------------------------------------


def _item_values(item: SourceItem) -> dict:
    data = asdict(item)
    data["category_name"] = data.pop("category")
    data.pop("external_id")
    return data


def upsert_items(source: ImportSource, items: list[SourceItem], now) -> dict:
    existing = dict(SupplierItem.objects.filter(source=source).values_list("external_id", "data_hash"))
    ids = dict(SupplierItem.objects.filter(source=source).values_list("external_id", "id"))
    to_create, to_update = [], []
    unchanged = 0
    for item in items:
        digest = item.digest()
        if item.external_id not in existing:
            to_create.append(
                SupplierItem(
                    source=source,
                    external_id=item.external_id,
                    data_hash=digest,
                    last_seen_at=now,
                    changed_at=now,
                    **_item_values(item),
                )
            )
        elif existing[item.external_id] != digest:
            obj = SupplierItem(pk=ids[item.external_id], data_hash=digest, changed_at=now, **_item_values(item))
            to_update.append(obj)
        else:
            unchanged += 1

    SupplierItem.objects.bulk_create(to_create, batch_size=BATCH)
    SupplierItem.objects.bulk_update(to_update, [*ITEM_FIELDS, "data_hash", "changed_at"], batch_size=BATCH)

    seen = [i.external_id for i in items]
    for start in range(0, len(seen), 2000):
        SupplierItem.objects.filter(source=source, external_id__in=seen[start : start + 2000]).update(
            last_seen_at=now, missing=False
        )
    missing = SupplierItem.objects.filter(source=source, last_seen_at__lt=now, missing=False).update(missing=True)
    return {
        "total": len(items),
        "new": len(to_create),
        "changed": len(to_update),
        "unchanged": unchanged,
        "missing": missing,
    }


def _variant_index(seller):
    variants = editable_variants(seller)
    by_barcode, by_sku = {}, {}
    for vid, code, barcode in variants.values_list("id", "code", "barcode"):
        if barcode:
            by_barcode[barcode.strip().lower()] = vid
        if code:
            by_sku[code.strip().lower()] = vid
    for vid, code in ProductBarcode.objects.filter(variant__in=variants).values_list("variant_id", "code"):
        by_barcode.setdefault(code.strip().lower(), vid)
    return by_barcode, by_sku


def auto_link(source: ImportSource) -> int:
    """Связывает новые позиции с нашими вариантами по штрихкоду, затем по артикулу (точное совпадение)."""
    by_barcode, by_sku = _variant_index(source.seller)
    taken = set(source.items.filter(variant__isnull=False).values_list("variant_id", flat=True))
    linked = []
    for item in source.items.filter(status=SupplierItem.NEW, variant__isnull=True).only("id", "barcode", "sku"):
        vid, method = None, ""
        if item.barcode and item.barcode.lower() in by_barcode:
            vid, method = by_barcode[item.barcode.lower()], "barcode"
        elif item.sku and item.sku.lower() in by_sku:
            vid, method = by_sku[item.sku.lower()], "sku"
        if vid and vid not in taken:  # один вариант — одна позиция этого поставщика
            taken.add(vid)
            item.variant_id, item.status, item.match_method = vid, SupplierItem.LINKED, method
            linked.append(item)
    SupplierItem.objects.bulk_update(linked, ["variant", "status", "match_method"], batch_size=BATCH)
    return len(linked)


def learn_barcodes(source: ImportSource) -> int:
    """
    Штрихкод из прайса → к связанному товару (доп. штрихкод для сканера). Товары, созданные раньше без заводского
    штрихкода (у них внутренний «2…»), получают его из первого же прайса, где он есть. Занятые коды не трогаем.
    """
    pairs = {
        code.strip(): vid
        for code, vid in source.items.filter(variant__isnull=False).exclude(barcode="").values_list("barcode", "variant_id")
        if code.strip()
    }
    if not pairs:
        return 0
    taken = {c.lower() for c in ProductBarcode.objects.filter(code__in=pairs).values_list("code", flat=True)}
    taken |= {c.lower() for c in ProductVariant.objects.filter(barcode__in=pairs).values_list("barcode", flat=True)}
    new = [ProductBarcode(code=code, variant_id=vid) for code, vid in pairs.items() if code.lower() not in taken]
    ProductBarcode.objects.bulk_create(new, batch_size=BATCH, ignore_conflicts=True)
    return len(new)


def _in_stock(item) -> bool:
    return not item.missing and bool(item.available or (item.quantity and item.quantity > 0))


def _linked_offers(variant_ids):
    return SupplierItem.objects.filter(
        variant_id__in=variant_ids, status=SupplierItem.LINKED, missing=False, source__is_active=True
    ).select_related("source")


def main_offers(variant_ids) -> dict[int, SupplierItem]:
    """
    Один товар у нескольких поставщиков: чья цена главная на витрине. {вариант: позиция поставщика}.
    Главный — у кого есть в наличии и дешевле закупка в гривнах (по курсу этого поставщика); ни у кого нет —
    у кого дешевле закупка. Цену задают только джерела с «Оновлювати ціни».
    """
    pricing: dict[int, Pricing] = {}
    best: dict[int, tuple] = {}
    for item in _linked_offers(variant_ids).filter(source__update_prices=True):
        cost = pricing.setdefault(item.source_id, Pricing(item.source)).cost(item)
        key = (not _in_stock(item), cost is None, cost or 0, item.source_id)
        if item.variant_id not in best or key < best[item.variant_id][0]:
            best[item.variant_id] = (key, item)
    return {vid: item for vid, (_key, item) in best.items()}


def apply_updates(source: ImportSource, items=None) -> dict:
    """Цены и видимость связанных вариантов. Если товар есть у нескольких поставщиков — цена от главного
    (main_offers), а скрывается товар, только когда его нет ни у кого и нет на своём складе."""
    stats = {"price_changed": 0, "hidden": 0, "shown": 0, "price_from_other": 0}
    qs = items if items is not None else source.items.filter(status=SupplierItem.LINKED, variant__isnull=False)
    allowed = set(editable_variants(source.seller).values_list("id", flat=True))
    linked = [item for item in qs.select_related("variant") if item.variant and item.variant_id in allowed]
    variant_ids = {item.variant_id for item in linked}
    main = main_offers(variant_ids)
    stocked = {item.variant_id for item in _linked_offers(variant_ids) if _in_stock(item)}
    # скрыт синхронизацией любого поставщика — вернуть может любой, у кого товар снова есть
    hidden: dict[int, dict[int, SupplierItem]] = {}
    for flagged in SupplierItem.objects.filter(variant_id__in=variant_ids, hidden_by_sync=True):
        hidden.setdefault(flagged.variant_id, {})[flagged.pk] = flagged
    pricing: dict[int, Pricing] = {}
    flags_changed = []

    for item in linked:
        variant = item.variant
        updates = {}
        offer = main.get(variant.pk)
        if offer is not None:
            prices = pricing.setdefault(offer.source_id, Pricing(offer.source))
            sale = prices.sale(offer)
            if sale is not None:
                fields = discount_fields(sale, prices.old(offer, sale))
                if (variant.price, variant.original_price, variant.discount) != (
                    fields["price"],
                    fields["original_price"],
                    fields["discount"],
                ):
                    updates.update(fields)
                    stats["price_changed"] += 1
                    stats["price_from_other"] += offer.source_id != source.pk
                cost = prices.cost(offer)
                if cost is not None and cost != variant.cost_price:
                    updates["cost_price"] = cost

        if source.hide_when_unavailable:
            supplier_has = variant.pk in stocked  # у любого из поставщиков, не только у этого
            own_stock = variant.stock - variant.reserved > 0
            if not supplier_has and not own_stock and variant.available:
                updates["available"] = False
                item.hidden_by_sync = True
                flags_changed.append(item)
                stats["hidden"] += 1
            elif supplier_has or own_stock:
                flagged = hidden.pop(variant.pk, {})
                if item.hidden_by_sync:
                    flagged[item.pk] = item
                if flagged:
                    updates["available"] = True
                    for hidden_item in flagged.values():
                        hidden_item.hidden_by_sync = False
                        flags_changed.append(hidden_item)
                    stats["shown"] += 1

        if updates:
            # update() вместо save(): save() пересчитывает цену по скидке и генерирует картинки штрихкодов
            ProductVariant.objects.filter(pk=variant.pk).update(**updates)
    SupplierItem.objects.bulk_update(flags_changed, ["hidden_by_sync"], batch_size=BATCH)
    return stats


# ---------------------------------------------------------------------------
# Остаток у поставщиков: продажа «под заказ» (свой склад не трогаем)
# ---------------------------------------------------------------------------


def _orderable(item) -> Decimal | None:
    """Сколько можно заказать по позиции фида. «Нет в наличии» важнее количества: O&L пишет 100 и у отсутствующих."""
    if item.available is False:
        return None
    if item.quantity is not None:
        return item.quantity if item.quantity > 0 else None
    return UNKNOWN_QTY if item.available else None


def _orderable_items(variant_ids):
    return SupplierItem.objects.filter(
        variant_id__in=variant_ids,
        status=SupplierItem.LINKED,
        missing=False,
        source__is_active=True,
        source__sell_on_order=True,
    ).select_related("source__supplier")


def refresh_supplier_stock(variant_ids) -> int:
    """Пересчитывает у вариантов supplier_qty / supplier_days по связанным позициям фидов. → сколько изменилось."""
    ids = {pk for pk in variant_ids if pk}
    if not ids:
        return 0
    qty: dict[int, Decimal] = {}
    days: dict[int, int] = {}
    for item in _orderable_items(ids):
        amount = _orderable(item)
        if amount is None:
            continue
        qty[item.variant_id] = qty.get(item.variant_id, Decimal(0)) + amount
        days[item.variant_id] = min(days.get(item.variant_id, item.source.order_days), item.source.order_days)
    changed = []
    for variant in ProductVariant.objects.filter(pk__in=ids).only("id", "supplier_qty", "supplier_days"):
        fresh = (qty.get(variant.pk), days.get(variant.pk))
        if (variant.supplier_qty, variant.supplier_days) != fresh:
            variant.supplier_qty, variant.supplier_days = fresh
            changed.append(variant)
    ProductVariant.objects.bulk_update(changed, ["supplier_qty", "supplier_days"], batch_size=BATCH)
    return len(changed)


def source_variant_ids(source: ImportSource) -> list[int]:
    return list(source.items.filter(variant__isnull=False).values_list("variant_id", flat=True))


def order_suppliers(variant_ids) -> dict:
    """{id варианта: поставщик, у кого заказать} — у кого есть и дешевле закупка (оценка — если в прайсе только РРЦ)."""
    best: dict[int, tuple] = {}
    for item in _orderable_items(variant_ids):
        if _orderable(item) is None or not item.source.supplier_id:
            continue
        cost = item.source.item_cost(item)
        key = (cost is None, cost or 0)
        if item.variant_id not in best or key < best[item.variant_id][0]:
            best[item.variant_id] = (key, item.source.supplier)
    return {vid: supplier for vid, (_key, supplier) in best.items()}


def schedule_next(source: ImportSource, now):
    source.next_sync_at = (
        now + timedelta(minutes=source.sync_interval_minutes) if source.sync_interval_minutes else None
    )


def sync_source(source: ImportSource, run: ImportRun | None = None) -> ImportRun:
    now = timezone.now()
    if run is None:
        run = ImportRun.objects.create(kind=ImportRun.KIND_SYNC, seller=source.seller, source=source)
    run.status, run.started_at = ImportRun.RUNNING, now
    run.save(update_fields=["status", "started_at"])
    source.last_status = "running"
    source.save(update_fields=["last_status"])

    try:
        catalog = get_connector(source).fetch()
        if not catalog.items:
            raise FormatError(_("Источник не вернул ни одного товара"))
        feed_rates = catalog.info.get("rates") or {}
        if feed_rates != (source.options or {}).get("feed_rates", {}):
            source.options = {**(source.options or {}), "feed_rates": feed_rates}
            source.save(update_fields=["options"])
        with transaction.atomic():
            stats = upsert_items(source, catalog.items, now)
            stats["linked_auto"] = auto_link(source)
            stats["barcodes_learned"] = learn_barcodes(source)
            stats.update(apply_updates(source))
            stats["on_order_changed"] = refresh_supplier_stock(source_variant_ids(source))
    except (ConnectorError, FetchError, FormatError) as exc:
        return _finish(source, run, now, error=str(exc))
    except Exception as exc:  # noqa: BLE001 — любой сбой фиксируем в журнале, а не теряем в воркере
        logger.exception("Синхронизация источника %s упала", source.pk)
        return _finish(source, run, now, error=_("Внутренняя ошибка: {error}").format(error=exc.__class__.__name__))

    stats["columns"] = catalog.info.get("columns", {})
    stats["format"] = catalog.info.get("format", "")
    stats["skipped"] = catalog.info.get("skipped", 0)
    stats["duplicates"] = catalog.info.get("duplicates", 0)
    stats["rates"] = catalog.info.get("rates", {})
    return _finish(source, run, now, stats=stats)


def _finish(source, run, now, *, stats=None, error=""):
    run.status = ImportRun.FAILED if error else ImportRun.DONE
    run.error = error
    run.stats = stats or {}
    run.finished_at = timezone.now()
    run.save(update_fields=["status", "error", "stats", "finished_at"])
    source.last_sync_at = now
    source.last_status = "error" if error else "ok"
    source.last_error = error
    schedule_next(source, now)
    source.save(update_fields=["last_sync_at", "last_status", "last_error", "next_sync_at"])
    return run


def due_sources(now=None):
    now = now or timezone.now()
    return ImportSource.objects.filter(is_active=True, sync_interval_minutes__gt=0).filter(
        Q(next_sync_at__isnull=True) | Q(next_sync_at__lte=now)
    )


def fail_stale_runs(hours: int = 2) -> int:
    """Запуски, «зависшие» после перезапуска воркера/Redis, помечаются ошибкой."""
    cutoff = timezone.now() - timedelta(hours=hours)
    stale = ImportRun.objects.filter(status__in=ImportRun.ACTIVE, created_at__lt=cutoff)
    ImportSource.objects.filter(runs__in=stale, last_status="running").update(last_status="error")
    return stale.update(
        status=ImportRun.FAILED, error=_("Задача не завершилась (перезапуск сервера?)"), finished_at=timezone.now()
    )


# ---------------------------------------------------------------------------
# Ручные действия с позициями поставщика
# ---------------------------------------------------------------------------


@transaction.atomic
def link_item(item: SupplierItem, variant_id: int) -> SupplierItem:
    variant = editable_variants(item.source.seller).filter(pk=variant_id).first()
    if variant is None:
        raise ImportActionError(_("Товар не найден или принадлежит другому продавцу"))
    other = item.source.items.filter(variant=variant).exclude(pk=item.pk).first()
    if other:
        raise ImportActionError(
            _("Этот товар уже связан с позицией «{name}»").format(name=other.name or other.external_id)
        )
    previous = item.variant_id
    item.variant, item.status, item.match_method, item.hidden_by_sync = variant, SupplierItem.LINKED, "manual", False
    item.save(update_fields=["variant", "status", "match_method", "hidden_by_sync"])
    apply_updates(item.source, SupplierItem.objects.filter(pk=item.pk))
    refresh_supplier_stock([previous, variant.pk])
    return item


def set_status(source: ImportSource, item_ids, status: str) -> int:
    qs = source.items.filter(pk__in=item_ids)
    if status == SupplierItem.NEW:
        unlinked = list(qs.filter(variant__isnull=False).values_list("variant_id", flat=True))
        changed = qs.update(status=SupplierItem.NEW, variant=None, match_method="", hidden_by_sync=False)
        refresh_supplier_stock(unlinked)
        return changed
    return qs.filter(variant__isnull=True).update(status=status)


def _brand(name: str, cache: dict):
    if not name:
        return None
    key = name.lower()
    if key not in cache:
        cache[key] = Brand.objects.filter(name__iexact=name).first() or Brand.objects.create(name=name)
    return cache[key]


def publish_items(source: ImportSource, item_ids, *, category: Category | None = None, visible: bool | None = None):
    """
    Создаёт товары из позиций поставщика (одна позиция → товар с одним вариантом).
    Если за это время появился наш вариант с таким штрихкодом/артикулом — позиция связывается с ним.
    → {"created": [variant_id…], "linked": n, "skipped": n}
    """
    pricing = Pricing(source)
    visible = source.publish_new if visible is None else visible
    # корень/раздел направления → товары раскладываются по подкатегориям (products/catalog/taxonomy.py)
    categories = CategoryResolver(category or source.category)
    by_barcode, by_sku = _variant_index(source.seller)
    taken = set(source.items.filter(variant__isnull=False).values_list("variant_id", flat=True))
    brands: dict = {}
    result = {"created": [], "linked": 0, "skipped": 0}

    items = source.items.filter(pk__in=item_ids, variant__isnull=True).exclude(status=SupplierItem.LINKED)
    for item in items:
        existing = by_barcode.get(item.barcode.lower()) if item.barcode else None
        existing = existing or (by_sku.get(item.sku.lower()) if item.sku else None)
        if existing and existing not in taken:
            item.variant_id, item.status, item.match_method = existing, SupplierItem.LINKED, "auto"
            item.save(update_fields=["variant", "status", "match_method"])
            taken.add(existing)
            result["linked"] += 1
            continue
        sale = pricing.sale(item)
        if not item.name or sale is None:
            result["skipped"] += 1
            continue
        with transaction.atomic():
            product = Product.objects.create(
                name=item.name[:255],
                seller=source.seller,
                category=categories.category_for(item.name, item.category_name or item.brand, item.params),
                description=item.description or None,
            )
            code_free = (
                item.sku and len(item.sku) <= 50 and not ProductVariant.objects.filter(code__iexact=item.sku).exists()
            )
            barcode_free = item.barcode and not ProductVariant.objects.filter(barcode=item.barcode).exists()
            variant = ProductVariant(
                product=product,
                variant_name=item.name[:255],
                code=item.sku if code_free else None,
                barcode=item.barcode if barcode_free else None,
                cost_price=pricing.cost(item),
                brand=_brand(item.brand[:255], brands),
                description=item.description or None,
                attributes=categories.attributes(item.name, item.description, item.params),
                available=visible,
                **NO_DIMENSIONS,
                **discount_fields(sale, pricing.old(item, sale)),
            )
            variant.save()
            item.variant, item.status, item.match_method = variant, SupplierItem.LINKED, "created"
            item.save(update_fields=["variant", "status", "match_method"])
        taken.add(variant.pk)
        result["created"].append((variant.pk, item.photos))
    refresh_supplier_stock(source.items.filter(pk__in=item_ids, variant__isnull=False).values_list("variant_id", flat=True))
    if visible and result["created"]:
        from app.apps.marketing.services import announce

        announce(
            list(
                ProductVariant.objects.filter(pk__in=[v for v, _p in result["created"]]).values_list(
                    "product_id", flat=True
                )
            )
        )
    return result


def sources_for(user, seller):
    if user.is_superuser:
        return ImportSource.objects.all()
    return ImportSource.objects.filter(seller=seller) if seller else ImportSource.objects.none()


def item_counts(source) -> dict:
    return source.items.aggregate(
        total=Count("id"),
        new=Count("id", filter=Q(status=SupplierItem.NEW)),
        linked=Count("id", filter=Q(status=SupplierItem.LINKED)),
        ignored=Count("id", filter=Q(status=SupplierItem.IGNORED)),
        missing=Count("id", filter=Q(missing=True)),
    )
