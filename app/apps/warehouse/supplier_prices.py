"""
Сравнение цен поставщиков на один и тот же товар.

Цены собираются из трёх мест — вносить их второй раз не нужно:
  feed    — прайс/фид источника (imports.SupplierItem, связанный с нашим вариантом): закупка, РРЦ, наличие;
  invoice — последний приход от поставщика (StockMovement «in» из накладной или операции): почём реально купили;
  manual  — цена, внесённая вручную (SupplierQuote): прайс в PDF, звонок, сайт поставщика.

Все цены пересчитываются в гривны по курсам CurrencyRate; «лучшая» — самая низкая закупка среди
поставщиков, у которых товар не отмечен как отсутствующий.
"""

from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Exists, OuterRef, Q

from app.apps.imports.models import SupplierItem
from app.apps.products.models import ProductVariant

from .models import CurrencyRate, StockMovement, SupplierQuote

CENT = Decimal("0.01")


@dataclass
class Offer:
    kind: str  # feed | invoice | manual
    supplier_key: str  # «s12» — поставщик из справочника, «src5» — источник без поставщика
    supplier_id: int | None
    supplier_name: str
    cost: Decimal | None  # закупочная цена в валюте поставщика
    currency: str
    cost_uah: Decimal | None
    rrp_uah: Decimal | None = None  # рекомендованная розничная (только из фида)
    available: bool | None = None
    quantity: Decimal | None = None
    date: datetime | None = None
    url: str = ""
    ref: str = ""  # название источника / № накладной / комментарий
    quote_id: int | None = None
    best: bool = False


def currency_rates() -> dict[str, Decimal]:
    rates = {code.upper(): rate for code, rate in CurrencyRate.objects.values_list("code", "rate")}
    rates["UAH"] = Decimal("1")
    return rates


def to_uah(amount, currency: str, rates: dict[str, Decimal]) -> Decimal | None:
    if amount is None:
        return None
    rate = rates.get((currency or "UAH").upper())
    return None if rate is None else (Decimal(amount) * rate).quantize(CENT, ROUND_HALF_UP)


def _feed_items(seller):
    qs = SupplierItem.objects.filter(
        status=SupplierItem.LINKED, missing=False, variant__isnull=False, source__is_active=True
    )
    return qs.filter(source__seller=seller) if seller else qs


def _receipts(seller):
    reversed_doc = StockMovement.objects.filter(
        inventory_document=OuterRef("inventory_document"), movement_type=StockMovement.IN_REVERSAL
    )
    qs = StockMovement.objects.filter(
        movement_type=StockMovement.IN, supplier__isnull=False, price_per_unit__isnull=False
    ).exclude(Exists(reversed_doc))
    return qs.filter(seller=seller) if seller else qs


def _quotes(seller):
    qs = SupplierQuote.objects.all()
    return qs.filter(seller=seller) if seller else qs


def supplier_keys(seller) -> dict[int, set[str]]:
    """{id варианта: ключи поставщиков} — по каким товарам вообще есть цены поставщиков (лёгкие запросы)."""
    keys: dict[int, set[str]] = defaultdict(set)
    variants = ProductVariant.objects.filter(product__seller=seller) if seller else None
    feeds = _feed_items(seller)
    receipts = _receipts(seller)
    quotes = _quotes(seller)
    if variants is not None:
        feeds, receipts, quotes = (qs.filter(variant__in=variants) for qs in (feeds, receipts, quotes))
    for vid, supplier_id, source_id in feeds.values_list("variant_id", "source__supplier_id", "source_id"):
        keys[vid].add(f"s{supplier_id}" if supplier_id else f"src{source_id}")
    for vid, supplier_id in receipts.values_list("variant_id", "supplier_id").distinct():
        keys[vid].add(f"s{supplier_id}")
    for vid, supplier_id in quotes.values_list("variant_id", "supplier_id"):
        keys[vid].add(f"s{supplier_id}")
    return keys


def collect_offers(variant_ids, seller) -> dict[int, list[Offer]]:
    """Все пропозиции поставщиков по вариантам, лучшая отмечена best=True; сортировка — от дешёвой."""
    rates = currency_rates()
    offers: dict[int, list[Offer]] = defaultdict(list)

    for item in _feed_items(seller).filter(variant_id__in=variant_ids).select_related("source__supplier"):
        source = item.source
        currency = item.currency or source.currency
        offers[item.variant_id].append(
            Offer(
                kind="feed",
                supplier_key=f"s{source.supplier_id}" if source.supplier_id else f"src{source.pk}",
                supplier_id=source.supplier_id,
                supplier_name=source.supplier.name if source.supplier_id else source.name,
                cost=item.cost,
                currency=currency,
                cost_uah=to_uah(item.cost, currency, rates),
                rrp_uah=to_uah(item.price, currency, rates),
                available=item.available,
                quantity=item.quantity,
                date=item.last_seen_at,
                url=item.url,
                ref=source.name,
            )
        )

    receipts = (
        _receipts(seller)
        .filter(variant_id__in=variant_ids)
        .select_related("supplier")
        .order_by("variant_id", "supplier_id", "-created_at")
        .distinct("variant_id", "supplier_id")  # последний приход от каждого поставщика (PostgreSQL)
    )
    for move in receipts:
        cost = (move.price_per_unit * move.exchange_rate).quantize(CENT, ROUND_HALF_UP)
        offers[move.variant_id].append(
            Offer(
                kind="invoice",
                supplier_key=f"s{move.supplier_id}",
                supplier_id=move.supplier_id,
                supplier_name=move.supplier.name,
                cost=cost,
                currency="UAH",
                cost_uah=cost,
                date=move.created_at,
                ref=move.document_number or "",
            )
        )

    for quote in _quotes(seller).filter(variant_id__in=variant_ids).select_related("supplier"):
        offers[quote.variant_id].append(
            Offer(
                kind="manual",
                supplier_key=f"s{quote.supplier_id}",
                supplier_id=quote.supplier_id,
                supplier_name=quote.supplier.name,
                cost=quote.price,
                currency=quote.currency,
                cost_uah=to_uah(quote.price, quote.currency, rates),
                available=quote.in_stock,
                date=quote.updated_at,
                ref=quote.note,
                quote_id=quote.pk,
            )
        )

    for items in offers.values():
        items.sort(key=lambda o: (o.cost_uah is None, o.cost_uah or 0, o.supplier_name))
        candidates = [o for o in items if o.cost_uah is not None and o.available is not False]
        if candidates:
            min(candidates, key=lambda o: o.cost_uah).best = True
    return offers


def _pct(part, whole) -> Decimal | None:
    if not whole:
        return None
    return (Decimal(part) / Decimal(whole) * 100).quantize(Decimal("0.1"), ROUND_HALF_UP)


def summarize(variant: ProductVariant, offers: list[Offer]) -> dict:
    priced = [o.cost_uah for o in offers if o.cost_uah is not None]
    best = next((o for o in offers if o.best), None)
    low, high = (min(priced), max(priced)) if priced else (None, None)
    price = variant.price
    cost_price = variant.cost_price
    return {
        "variant_id": variant.pk,
        "product_id": variant.product_id,
        "name": variant.variant_name or (variant.product.name if variant.product_id else "") or f"#{variant.pk}",
        "code": variant.code or "",
        "barcode": variant.barcode or "",
        "price": price,
        "cost_price": cost_price,
        "suppliers": len({o.supplier_key for o in offers}),
        "min_cost": low,
        "max_cost": high,
        # насколько дороже самый дорогой поставщик самого дешёвого
        "spread_pct": _pct(high - low, low) if priced else None,
        "best": {"supplier_name": best.supplier_name, "cost_uah": best.cost_uah, "kind": best.kind} if best else None,
        # наценка, если брать у лучшего поставщика
        "margin_pct": _pct(price - best.cost_uah, price) if best and price else None,
        # сколько сэкономим на каждой штуке против текущей себестоимости
        "saving": (cost_price - best.cost_uah) if best and cost_price and cost_price > best.cost_uah else None,
        "offers": [asdict(o) for o in offers],
    }


SORTS = {
    "spread": lambda row: (row["spread_pct"] is None, -(row["spread_pct"] or 0), row["name"]),
    "saving": lambda row: (row["saving"] is None, -(row["saving"] or 0), row["name"]),
    "name": lambda row: (row["name"].lower(),),
}


def comparison(seller, *, search: str = "", multi: bool = False, sort: str = "spread") -> list[dict]:
    """Таблица сравнения для кабинета: товары, по которым есть цены поставщиков."""
    keys = supplier_keys(seller)
    ids = [vid for vid, suppliers in keys.items() if not multi or len(suppliers) > 1]
    variants = ProductVariant.objects.filter(pk__in=ids).select_related("product")
    search = search.strip()
    if search:
        variants = variants.filter(
            Q(variant_name__icontains=search)
            | Q(product__name__icontains=search)
            | Q(code__icontains=search)
            | Q(barcode=search)
        )
    variants = list(variants)
    offers = collect_offers([v.pk for v in variants], seller)
    rows = [summarize(v, offers.get(v.pk, [])) for v in variants]
    rows.sort(key=SORTS.get(sort, SORTS["spread"]))
    return rows
