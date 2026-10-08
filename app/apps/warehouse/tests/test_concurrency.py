"""Гонки: одновременные резервы/списания не должны приводить к оверселлу."""
import threading
from decimal import Decimal

import pytest
from django.db import connection

from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.tests.factories import SupplierFactory, WarehouseFactory


def _run_parallel(fn, n):
    results, barrier = [], threading.Barrier(n)

    def worker():
        try:
            barrier.wait()
            fn()
            results.append("ok")
        except stock.InsufficientStockError:
            results.append("insufficient")
        finally:
            connection.close()

    threads = [threading.Thread(target=worker) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


@pytest.mark.django_db(transaction=True)
def test_parallel_reserve_never_oversells():
    wh = WarehouseFactory(is_default=True)
    variant = ProductVariantFactory()
    stock.receive(variant, wh, 5, supplier=SupplierFactory())

    results = _run_parallel(lambda: stock.reserve([(variant.pk, 1)]), 10)

    v = ProductVariant.objects.get(pk=variant.pk)
    assert results.count("ok") == 5
    assert results.count("insufficient") == 5
    assert v.reserved == Decimal("5")
    assert v.available_stock == 0


@pytest.mark.django_db(transaction=True)
def test_parallel_write_off_never_negative():
    wh = WarehouseFactory(is_default=True)
    variant = ProductVariantFactory()
    stock.receive(variant, wh, 3, supplier=SupplierFactory())

    results = _run_parallel(lambda: stock.write_off(variant.pk, wh, 1), 8)

    v = ProductVariant.objects.get(pk=variant.pk)
    assert results.count("ok") == 3
    assert v.stock == 0
    assert stock.get_balance(variant, wh) == 0
    assert stock.journal_balance(variant.pk) == 0
