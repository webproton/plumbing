"""Статистика продаж владельца: выручка, прибыль по закупке на момент заказа, отмены, прошлый период, склад."""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from app.apps.accounts.tests.factories import UserFactory
from app.apps.orders import services
from app.apps.orders.models import Order
from app.apps.orders.stats import sales_stats
from app.apps.orders.tests.test_manage import _client, _order, _variant
from app.apps.products.models import ProductVariant
from app.apps.warehouse.tests.factories import SellerFactory

pytestmark = pytest.mark.django_db
STATS = "orders:manage-order-stats"


def _cost(variant, cost):
    ProductVariant.objects.filter(pk=variant.pk).update(cost_price=Decimal(cost) if cost is not None else None)
    return ProductVariant.objects.get(pk=variant.pk)


def test_revenue_profit_cancellations_and_previous_period():
    seller, other = SellerFactory(), SellerFactory()
    tap = _cost(_variant(seller, qty=10, price="100.00"), "60")  # закупка известна
    hose = _cost(_variant(seller, qty=10, price="50.00"), None)  # закупки нет — прибыль только по смесителю
    theirs = _variant(other, qty=10, price="999.00")

    _order((tap, 2), (theirs, 1))  # смешанный заказ: продавец видит только свою часть
    _order((hose, 1))
    canceled = _order((tap, 1))
    services.change_status(canceled, Order.STATUS.canceled)
    old = _order((tap, 1))
    Order.objects.filter(pk=old.pk).update(creation_date=timezone.now() - timedelta(days=40))
    _cost(tap, "90")  # себестоимость выросла после заказов — прибыль считаем по закупке на момент заказа

    stats = sales_stats(seller.user, 30)
    assert (stats["revenue"], stats["orders"], stats["avg_check"]) == (Decimal("250.00"), 2, Decimal("125.00"))
    assert stats["profit"] == Decimal("80.00")  # (100 − 60) × 2
    assert stats["profit_coverage"] == 80  # 200 из 250 грн — с известной закупкой
    assert stats["canceled"] == 1
    assert stats["previous"]["revenue"] == Decimal("100.00")  # заказ 40 дней назад
    assert stats["top_products"][0]["variant_id"] == tap.pk and stats["top_products"][0]["qty"] == 2
    assert len(stats["by_day"]) == 30 and sum(d["revenue"] for d in stats["by_day"]) == Decimal("250.00")


def test_dead_stock_low_stock_and_on_order():
    seller = SellerFactory()
    shelf = _cost(_variant(seller, qty=5, price="40.00"), "20")  # лежит без продаж
    last = _variant(seller, qty=3, price="30.00")  # продали 1 — доступно 2, заканчивается
    _order((last, 1))

    stats = sales_stats(seller.user, 30)
    dead = {item["variant_id"]: item for item in stats["dead_stock"]["items"]}
    assert shelf.pk in dead and dead[shelf.pk]["value"] == Decimal("100.00")
    assert last.pk not in dead
    assert [row["variant_id"] for row in stats["low_stock"]] == [last.pk]
    assert stats["low_stock"][0]["available"] == 2
    assert stats["on_order_open"] == {"lines": 0, "orders": 0}


def test_api_period_and_access():
    seller = SellerFactory()
    client = _client(seller.user)
    assert client.get(reverse(STATS), {"days": 7}).json()["period"]["days"] == 7
    assert client.get(reverse(STATS), {"days": 13}).status_code == 400
    assert _client(UserFactory()).get(reverse(STATS)).status_code == 403
