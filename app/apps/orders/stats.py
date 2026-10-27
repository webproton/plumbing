"""
Статистика продаж для владельца магазина: выручка, заказы, средний чек, прибыль, топ товаров и разделов,
«мёртвый» склад, что заканчивается, что ждёт заказа у поставщика.

Продажа — строка заказа, который не отменён. Продавец видит только строки своих товаров (в смешанном
заказе — свою часть), администратор — весь магазин. Прибыль — по закупке на момент заказа
(OrderItem.unit_cost), для старых заказов — по текущей себестоимости товара.
"""

from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db.models import Count, DecimalField, ExpressionWrapper, F, Max, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from app.apps.products.models import ProductVariant
from app.apps.warehouse.permissions import get_active_seller

from .models import Order, OrderItem

PERIODS = (1, 7, 30, 90, 365)
LOW_STOCK = 3  # «заканчивается»: доступно столько или меньше, а товар продаётся
TOP = 10
CLOSED = (Order.STATUS.delivered, Order.STATUS.completed, Order.STATUS.canceled)
ZERO = Decimal("0")
MONEY = DecimalField(max_digits=16, decimal_places=4)


def _money(value) -> Decimal:
    return (value or ZERO).quantize(Decimal("0.01"))


def _scope(user):
    """(строки заказов, варианты товаров), которые видит пользователь."""
    if user.is_superuser:
        return OrderItem.objects.all(), ProductVariant.objects.all()
    seller = get_active_seller(user)
    if seller is None:
        return OrderItem.objects.none(), ProductVariant.objects.none()
    return OrderItem.objects.filter(product__seller=seller), ProductVariant.objects.filter(product__seller=seller)


def _bounds(days: int, now):
    """Период — последние days дней включая сегодня (по Киеву); предыдущий — столько же дней до него."""
    today = timezone.localdate(now)
    start = timezone.make_aware(datetime.combine(today - timedelta(days=days - 1), time.min))
    return start, now, start - timedelta(days=days)


LINE = ExpressionWrapper(F("unit_price") * F("quantity"), output_field=MONEY)
COST = Coalesce("unit_cost", "variant__cost_price")
PROFIT = ExpressionWrapper((F("unit_price") - COST) * F("quantity"), output_field=MONEY)


def _totals(items) -> dict:
    sold = items.exclude(order__status_order=Order.STATUS.canceled)
    agg = sold.aggregate(
        revenue=Sum(LINE),
        orders=Count("order", distinct=True),
        units=Sum("quantity"),
        profit=Sum(PROFIT, filter=Q(unit_cost__isnull=False) | Q(variant__cost_price__isnull=False)),
        revenue_with_cost=Sum(LINE, filter=Q(unit_cost__isnull=False) | Q(variant__cost_price__isnull=False)),
    )
    revenue, orders = _money(agg["revenue"]), agg["orders"] or 0
    return {
        "revenue": revenue,
        "orders": orders,
        "avg_check": _money(revenue / orders) if orders else ZERO,
        "units": agg["units"] or ZERO,
        "profit": _money(agg["profit"]),
        # доля выручки, по которой известна закупка: 100 — прибыль точная, меньше — оценка снизу
        "profit_coverage": round(float(agg["revenue_with_cost"] or 0) / float(revenue) * 100) if revenue else 100,
        "canceled": items.filter(order__status_order=Order.STATUS.canceled).values("order").distinct().count(),
    }


def sales_stats(user, days: int = 30, now=None) -> dict:
    now = now or timezone.now()
    start, end, prev_start = _bounds(days, now)
    items, variants = _scope(user)
    period = items.filter(order__creation_date__gte=start, order__creation_date__lte=end)
    previous = items.filter(order__creation_date__gte=prev_start, order__creation_date__lt=start)
    sold = period.exclude(order__status_order=Order.STATUS.canceled)

    # по дням — в Python: в Postgres образа postgis 14 нет пояса «Europe/Kyiv» (старое имя Europe/Kiev)
    by_day: dict = {}
    for created, order_id, line in sold.annotate(line=LINE).values_list("order__creation_date", "order_id", "line"):
        day = by_day.setdefault(timezone.localdate(created), {"revenue": ZERO, "orders": set()})
        day["revenue"] += line or ZERO
        day["orders"].add(order_id)
    days_list = [timezone.localdate(start) + timedelta(days=i) for i in range(days)]

    top_products = (
        sold.values("variant_id", "product_id", "name")
        .annotate(qty=Sum("quantity"), revenue=Sum(LINE), profit=Sum(PROFIT))
        .order_by("-revenue")[:TOP]
    )
    top_categories = (
        sold.values(category=F("product__category__name"))
        .annotate(qty=Sum("quantity"), revenue=Sum(LINE))
        .order_by("-revenue")[:8]
    )

    sold_ids = set(sold.values_list("variant_id", flat=True))
    # «мёртвый» склад: свой остаток есть, а за период ни одной продажи — деньги лежат на полке
    shelf_value = ExpressionWrapper(F("stock") * Coalesce("cost_price", ZERO), output_field=MONEY)
    dead_base = variants.filter(stock__gt=0).exclude(pk__in=sold_ids)
    dead_agg = dead_base.aggregate(count=Count("pk"), value=Sum(shelf_value))
    not_canceled = ~Q(order_items__order__status_order=Order.STATUS.canceled)
    dead = dead_base.annotate(
        value=shelf_value, last_sold=Max("order_items__order__creation_date", filter=not_canceled)
    )
    low = (
        variants.filter(pk__in=sold_ids)
        .annotate(free=F("stock") - F("reserved"))  # «available» занято полем «показывать на сайте»
        .filter(free__lte=LOW_STOCK)
        .exclude(stock=0, supplier_qty__gt=0)  # своего не было — продаётся под заказ у поставщика, не «заканчивается»
        .annotate(sold=Sum("order_items__quantity", filter=Q(order_items__in=sold)))
        .order_by("free", "-sold")[:TOP]
    )
    on_order = items.filter(on_order=True).exclude(order__status_order__in=CLOSED)

    return {
        "period": {"days": days, "from": timezone.localdate(start), "to": timezone.localdate(end)},
        **_totals(period),
        "previous": {k: v for k, v in _totals(previous).items() if k in ("revenue", "orders", "avg_check", "profit")},
        "by_day": [
            {
                "date": d,
                "revenue": _money((by_day.get(d) or {}).get("revenue")),
                "orders": len((by_day.get(d) or {}).get("orders", ())),
            }
            for d in days_list
        ],
        "top_products": [
            {**row, "revenue": _money(row["revenue"]), "profit": _money(row["profit"])} for row in top_products
        ],
        "top_categories": [
            {"category": row["category"] or "—", "qty": row["qty"], "revenue": _money(row["revenue"])}
            for row in top_categories
        ],
        "dead_stock": {
            "count": dead_agg["count"] or 0,
            "value": _money(dead_agg["value"]),
            "items": [
                {
                    "variant_id": v.pk,
                    "product_id": v.product_id,
                    "name": v.variant_name or v.product.name,
                    "stock": v.stock,
                    "value": _money(v.value),
                    "last_sold": timezone.localdate(v.last_sold) if v.last_sold else None,
                }
                for v in dead.select_related("product").order_by("-value")[:TOP]
            ],
        },
        "low_stock": [
            {
                "variant_id": v.pk,
                "product_id": v.product_id,
                "name": v.variant_name or v.product.name,
                "available": v.free,
                "sold": v.sold or ZERO,
            }
            for v in low.select_related("product")
        ],
        "on_order_open": {"lines": on_order.count(), "orders": on_order.values("order").distinct().count()},
    }
