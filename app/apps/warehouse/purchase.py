"""
Список закупки: «що докупити» — пишут как удобно, строки становятся объектами заказа.

  «футорки 20 1/2 в — 10 шт» → что искать «футорки 20 1/2 в», количество 10, «шт».
Подбор для строки (options):
  last_time  — что брали в прошлый раз по такой же записи (тот же товар и поставщик);
  products   — свои товары по умному поиску + предложения всех поставщиков (прайс, прошлый приход, ручная цена;
               supplier_prices.collect_offers), самое дешёвое отмечено;
  items      — позиции прайсов поставщиков, которых ещё нет в каталоге (закупка по прайсу).
Новая строка сама берёт «як минулого разу» или единственный найденный товар с лучшим поставщиком — человек
видит, что выбрано, и может поменять одной кнопкой.
«Зібрати замовлення» — строки по поставщикам с суммами и готовым текстом для Viber/Telegram/почты.
"""

import re
from decimal import Decimal, InvalidOperation

from django.db.models import Q
from django.utils import timezone

from app.apps.imports.models import SupplierItem
from app.apps.imports.services import Pricing, item_search_q, sources_for
from app.apps.products.models import ProductVariant
from app.apps.products.search import compact_q, match_all, suggest, vocab_tokens

from .models import PurchaseLine, PurchaseList, Supplier
from .supplier_prices import collect_offers

UNITS = {
    "шт": "шт", "штук": "шт", "штуки": "шт", "штука": "шт", "штук.": "шт", "pcs": "шт",
    "м": "м", "метр": "м", "метра": "м", "метрів": "м", "метров": "м", "мп": "м",
    "пар": "пар", "пари": "пар", "пара": "пар", "пары": "пар",
    "кг": "кг", "уп": "уп", "упак": "уп", "упаковка": "уп", "упаковки": "уп", "пачка": "уп", "пачки": "уп",
    "рул": "рул", "рулон": "рул", "рулони": "рул", "рулона": "рул", "бухта": "бух", "бухти": "бух", "бухты": "бух",
    "компл": "компл", "комплект": "компл", "комплекти": "компл",
}
_UNIT = "|".join(sorted((re.escape(u) for u in UNITS), key=len, reverse=True))
# «— 10 шт», «10шт», «x10», «х 10», «*10», «по 10» в конце строки; число с единицей — где угодно
_QTY_WITH_UNIT = re.compile(rf"(?<![\w/.,])(\d+(?:[.,]\d+)?)\s*({_UNIT})(?!\w)", re.IGNORECASE)
_QTY_TIMES = re.compile(r"(?:^|\s)[xх×*]\s*(\d+(?:[.,]\d+)?)\s*$|(?:^|\s)(?:—|–|-|по)\s*(\d+(?:[.,]\d+)?)\s*$", re.IGNORECASE)
OPTIONS_LIMIT = 6


def parse_line(text: str) -> tuple[str, Decimal, str]:
    """«футорки 20 1/2 в — 10 шт» → («футорки 20 1/2 в», 10, «шт»). Без количества — 1: размеры («16», «1/2») не трогаем."""
    text = " ".join((text or "").split())
    quantity, unit = Decimal(1), ""
    matches = list(_QTY_WITH_UNIT.finditer(text))
    match = matches[-1] if matches else None  # количество пишут в конце: «шланг 1 м — 5 шт» → 5 шт
    if match:
        quantity, unit = _number(match.group(1)), UNITS[match.group(2).lower()]
        text = (text[: match.start()] + text[match.end():]).strip()
    else:
        times = _QTY_TIMES.search(text)
        if times:
            quantity = _number(times.group(1) or times.group(2))
            text = text[: times.start()].strip()
    text = text.strip(" -—–,.:;")
    return text, (quantity if quantity > 0 else Decimal(1)), unit


def _number(raw: str) -> Decimal:
    try:
        return Decimal(raw.replace(",", "."))
    except InvalidOperation:
        return Decimal(1)


def qty_text(value: Decimal) -> str:
    """10.000 → «10», 2.500 → «2.5» (без «1E+1»)."""
    return f"{value.normalize():f}"


def key_of(text: str) -> str:
    """Запись для памяти «як минулого разу»: без регистра, лишних пробелов и знаков."""
    return " ".join(re.findall(r"[^\W_]+", (text or "").lower().replace("ё", "е")))


# --- списки ---
def current_list(seller, user=None) -> PurchaseList:
    plist = PurchaseList.objects.filter(seller=seller, status=PurchaseList.DRAFT).order_by("-created_at").first()
    return plist or PurchaseList.objects.create(seller=seller, created_by=user)


def add_lines(plist: PurchaseList, user, texts=(), variant_ids=()) -> list[PurchaseLine]:
    """Новые строки: из текста (каждая строка — отдельная запись) или из товаров (кнопка «У закупку» в остатках)."""
    position = (plist.lines.order_by("-position").values_list("position", flat=True).first() or 0) + 1
    created = []
    for raw in texts:
        query, quantity, unit = parse_line(raw)
        if not query:
            continue
        line = PurchaseLine.objects.create(purchase_list=plist, position=position, text=query, quantity=quantity, unit=unit)
        _auto_pick(line, user)
        created.append(line)
        position += 1
    for variant in ProductVariant.objects.filter(pk__in=variant_ids, product__seller=plist.seller).select_related("product"):
        line = PurchaseLine.objects.create(
            purchase_list=plist, position=position, text=variant.variant_name or variant.product.name, variant=variant
        )
        _pick_supplier(line)
        created.append(line)
        position += 1
    return created


def _previous(line: PurchaseLine) -> PurchaseLine | None:
    """Та же запись в прошлых списках этого продавца, где товар был выбран."""
    key = key_of(line.text)
    candidates = (
        PurchaseLine.objects.filter(purchase_list__seller=line.purchase_list.seller)
        .exclude(pk=line.pk)
        .filter(Q(variant__isnull=False) | Q(supplier_item__isnull=False))
        .select_related("variant__product", "supplier", "supplier_item")
        .order_by("-purchase_list__created_at", "-id")
    )
    return next((c for c in candidates[:500] if key_of(c.text) == key), None)


def _auto_pick(line: PurchaseLine, user) -> None:
    previous = _previous(line)
    if previous:
        line.variant, line.supplier_item = previous.variant, previous.supplier_item
        line.supplier, line.supplier_label, line.price_uah = previous.supplier, previous.supplier_label, previous.price_uah
        if previous.unit and not line.unit:
            line.unit = previous.unit
        line.auto = True
        line.save()
        if line.variant_id:
            _refresh_price(line)
        return
    found = list(_own_variants(line.purchase_list.seller, line.text)[:2])
    if len(found) == 1:  # нашёлся ровно один свой товар — берём его и лучшего поставщика
        line.variant, line.auto = found[0], True
        line.save(update_fields=["variant", "auto"])
        _pick_supplier(line)


def _pick_supplier(line: PurchaseLine) -> None:
    offers = collect_offers([line.variant_id], line.purchase_list.seller).get(line.variant_id, [])
    best = next((o for o in offers if o.best), None) or (offers[0] if offers else None)
    if best:
        _apply_offer(line, best.supplier_id, best.supplier_name, best.cost_uah)
    line.save()


def _refresh_price(line: PurchaseLine) -> None:
    """Цена у того же поставщика — сегодняшняя (прайс мог измениться)."""
    offers = collect_offers([line.variant_id], line.purchase_list.seller).get(line.variant_id, [])
    same = next((o for o in offers if (o.supplier_id and o.supplier_id == line.supplier_id) or
                 (not o.supplier_id and o.supplier_name == line.supplier_label)), None)
    if same and same.cost_uah is not None:
        line.price_uah = same.cost_uah
        line.save(update_fields=["price_uah"])


def _apply_offer(line: PurchaseLine, supplier_id, supplier_name: str, cost_uah) -> None:
    line.supplier_id = supplier_id
    line.supplier_label = "" if supplier_id else supplier_name
    line.price_uah = cost_uah


# --- подбор ---
def _own_variants(seller, query: str):
    variants = ProductVariant.objects.filter(product__seller=seller).select_related("product", "brand")
    found = Q(code__iexact=query) | Q(barcode__iexact=query)
    words = match_all(
        query,
        lambda w: Q(product__name__icontains=w) | Q(variant_name__icontains=w) | Q(brand__name__icontains=w) | Q(code__icontains=w),
    )
    if words is not None:
        found |= words
    if (glued := compact_q(query, "product__name", "variant_name", "code")) is not None:
        found |= glued
    return variants.filter(found).order_by("-available", "variant_name", "id")


def options(line: PurchaseLine, user) -> dict:
    """Чем может быть строка: «як минулого разу», свои товары с предложениями поставщиков, позиции прайсов."""
    seller = line.purchase_list.seller
    query = line.text
    own = list(_own_variants(seller, query)[:OPTIONS_LIMIT])
    suggestion = None
    items = list(_supplier_items(user, seller, query)[:OPTIONS_LIMIT])
    if not own and not items:
        texts = (t for row in ProductVariant.objects.filter(product__seller=seller).values_list("product__name", "code") for t in row)
        fixed = suggest(query, vocab_tokens(texts))
        if fixed:
            own, items, suggestion = list(_own_variants(seller, fixed)[:OPTIONS_LIMIT]), list(_supplier_items(user, seller, fixed)[:OPTIONS_LIMIT]), fixed
    offers = collect_offers([v.pk for v in own], seller) if own else {}
    previous = _previous(line)
    return {
        "suggestion": suggestion,
        "last_time": _line_choice(previous) if previous else None,
        "products": [
            {
                "variant": v.pk,
                "name": v.variant_name or v.product.name,
                "sku": v.code or "",
                "stock": str(v.stock - v.reserved),
                "offers": [
                    {
                        "supplier": o.supplier_id,
                        "supplier_name": o.supplier_name,
                        "price": str(o.cost_uah) if o.cost_uah is not None else None,
                        "kind": o.kind,  # feed — прайс, invoice — прошлый приход, manual — вручную
                        "date": o.date.isoformat() if o.date else None,
                        "available": o.available,
                        "best": o.best,
                    }
                    for o in offers.get(v.pk, [])
                ],
            }
            for v in own
        ],
        "items": [_item_choice(item) for item in items],
    }


def _supplier_items(user, seller, query: str):
    sources = sources_for(user, seller)
    return (
        SupplierItem.objects.filter(source__in=sources, missing=False, status=SupplierItem.NEW)
        .filter(item_search_q(query))
        .select_related("source__supplier")
        .order_by("-available", "name", "id")
    )


def _item_cost(item: SupplierItem):
    pricing = Pricing(item.source)
    cost = pricing.cost(item)
    if cost is None:  # в прайсе только РРЦ — закупка по правилам поставщика (РРЦ минус скидка)
        cost = item.source.item_cost(item)
        rate = pricing.rate(item.currency or item.source.currency)
        cost = (cost * rate).quantize(Decimal("0.01")) if cost is not None and rate is not None else None
    return cost.quantize(Decimal("0.01")) if cost is not None else None


def _item_choice(item: SupplierItem) -> dict:
    source = item.source
    cost = _item_cost(item)
    return {
        "item": item.pk,
        "name": item.name,
        "sku": item.sku,
        "supplier": source.supplier_id,
        "supplier_name": source.supplier.name if source.supplier_id else source.name,
        "price": str(cost) if cost is not None else None,
        "raw_price": str(item.cost or item.price) if (item.cost or item.price) else None,
        "currency": item.currency,
        "available": item.available,
    }


def _line_choice(line: PurchaseLine) -> dict:
    return {
        "variant": line.variant_id,
        "item": line.supplier_item_id,
        "name": (line.variant.variant_name or line.variant.product.name) if line.variant_id else (line.supplier_item.name if line.supplier_item_id else ""),
        "supplier": line.supplier_id,
        "supplier_name": line.supplier.name if line.supplier_id else line.supplier_label,
        "price": str(line.price_uah) if line.price_uah is not None else None,
        "date": line.purchase_list.created_at.isoformat(),
    }


def choose(line: PurchaseLine, *, variant=None, item=None, supplier=None, supplier_name="", price=None, clear=False) -> PurchaseLine:
    """Человек выбрал: свой товар (и поставщика из его предложений), позицию прайса или «нічого з цього»."""
    seller = line.purchase_list.seller
    if clear:
        line.variant = line.supplier_item = line.supplier = None
        line.supplier_label, line.price_uah = "", None
    elif item is not None:
        chosen = SupplierItem.objects.select_related("source__supplier").get(pk=item, source__seller=seller)
        line.supplier_item, line.variant = chosen, chosen.variant
        choice = _item_choice(chosen)
        _apply_offer(line, choice["supplier"], choice["supplier_name"], Decimal(choice["price"]) if choice["price"] else None)
    elif variant is not None:
        line.variant = ProductVariant.objects.get(pk=variant, product__seller=seller)
        line.supplier_item = None
        if supplier is not None or supplier_name:
            supplier_obj = Supplier.objects.filter(pk=supplier).first() if supplier else None
            _apply_offer(line, supplier_obj.pk if supplier_obj else None, supplier_name, Decimal(price) if price else None)
        else:
            line.save()
            _pick_supplier(line)
    line.auto = False
    line.save()
    return line


# --- собрать заказ ---
def assemble(plist: PurchaseList) -> dict:
    """Строки по поставщикам: у кого что заказать, суммы и текст для отправки. Без поставщика — отдельная группа."""
    groups: dict[str, dict] = {}
    for line in plist.lines.select_related("variant__product", "supplier", "supplier_item"):
        name = (line.variant.variant_name or line.variant.product.name) if line.variant_id else (
            line.supplier_item.name if line.supplier_item_id else line.text
        )
        if line.supplier_id:
            key, title, phone = f"s{line.supplier_id}", line.supplier.name, line.supplier.phone
        elif line.supplier_label:
            key, title, phone = f"l:{line.supplier_label}", line.supplier_label, ""
        else:
            key, title, phone = "none", "", ""
        group = groups.setdefault(key, {"key": key, "supplier": title, "phone": phone, "lines": [], "total": Decimal(0)})
        total = (line.price_uah * line.quantity).quantize(Decimal("0.01")) if line.price_uah is not None else None
        sku = (line.variant.code if line.variant_id else (line.supplier_item.sku if line.supplier_item_id else "")) or ""
        if sku and sku.lower() in name.lower():
            sku = ""  # артикул уже в названии («… (ZX4792)») — не дублируем
        group["lines"].append(
            {
                "id": line.pk,
                "text": line.text,
                "name": name,
                "sku": sku,
                "quantity": qty_text(line.quantity),
                "unit": line.unit or "шт",
                "price": str(line.price_uah) if line.price_uah is not None else None,
                "total": str(total) if total is not None else None,
            }
        )
        if total is not None:
            group["total"] += total
    result = []
    for group in sorted(groups.values(), key=lambda g: (g["key"] == "none", g["supplier"])):
        lines = [f"{i}. {r['name']}{' (' + r['sku'] + ')' if r['sku'] else ''} — {r['quantity']} {r['unit']}" for i, r in enumerate(group["lines"], 1)]
        group["message"] = "\n".join([f"Замовлення від {plist.seller.shop_name}:", *lines])
        group["total"] = str(group["total"].quantize(Decimal("0.01")))
        result.append(group)
    return {"groups": result, "lines": plist.lines.count()}


def mark_ordered(plist: PurchaseList) -> PurchaseList:
    plist.status, plist.ordered_at = PurchaseList.ORDERED, timezone.now()
    plist.save(update_fields=["status", "ordered_at"])
    return plist


def serialize_line(line: PurchaseLine) -> dict:
    return {
        "id": line.pk,
        "text": line.text,
        "quantity": qty_text(line.quantity),
        "unit": line.unit,
        "auto": line.auto,
        "choice": _line_choice(line) if (line.variant_id or line.supplier_item_id) else None,
        "supplier_name": line.supplier.name if line.supplier_id else line.supplier_label,
        "price": str(line.price_uah) if line.price_uah is not None else None,
    }


def serialize_list(plist: PurchaseList) -> dict:
    lines = plist.lines.select_related("variant__product", "supplier", "supplier_item", "purchase_list")
    return {"id": plist.pk, "status": plist.status, "created_at": plist.created_at.isoformat(),
            "lines": [serialize_line(line) for line in lines]}

