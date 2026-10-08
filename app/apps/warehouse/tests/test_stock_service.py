from decimal import Decimal

import pytest

from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.models import StockBalance, StockMovement
from app.apps.warehouse.tests.factories import SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def wh():
    return WarehouseFactory(is_default=True)


@pytest.fixture
def variant():
    return ProductVariantFactory()


@pytest.fixture
def supplier():
    return SupplierFactory()


def _fresh(variant):
    return ProductVariant.objects.get(pk=variant.pk)


def test_receive_updates_journal_balance_and_cache(variant, wh, supplier):
    stock.receive(variant, wh, "2.5", supplier=supplier, price_per_unit=D("10.1234"))
    stock.receive(variant, wh, 3, supplier=supplier)

    assert _fresh(variant).stock == D("5.5")
    assert StockBalance.objects.get(variant=variant, warehouse=wh).quantity == D("5.5")
    assert StockMovement.objects.filter(variant=variant).count() == 2
    assert stock.journal_balance(variant.pk) == D("5.5")


def test_receive_requires_supplier(variant, wh):
    with pytest.raises(stock.StockError):
        stock.receive(variant, wh, 1)


@pytest.mark.parametrize("bad", [0, -1, "abc", None])
def test_quantity_must_be_positive_number(variant, wh, supplier, bad):
    with pytest.raises(stock.StockError):
        stock.receive(variant, wh, bad, supplier=supplier)


def test_write_off_cannot_go_negative(variant, wh, supplier):
    stock.receive(variant, wh, 2, supplier=supplier)
    with pytest.raises(stock.InsufficientStockError):
        stock.write_off(variant, wh, 3)
    assert _fresh(variant).stock == 2
    assert StockMovement.objects.filter(movement_type=StockMovement.OUT).count() == 0


def test_write_off_does_not_consume_reserved(variant, wh, supplier):
    stock.receive(variant, wh, 5, supplier=supplier)
    stock.reserve([(variant, 4)])
    with pytest.raises(stock.InsufficientStockError):
        stock.write_off(variant, wh, 2)
    stock.write_off(variant, wh, 1)
    v = _fresh(variant)
    assert (v.stock, v.reserved, v.available_stock) == (4, 4, 0)


def test_transfer_moves_between_warehouses_total_unchanged(variant, wh, supplier):
    other = WarehouseFactory(seller=wh.seller)
    stock.receive(variant, wh, 10, supplier=supplier)
    stock.transfer(variant, wh, other, 4)

    assert stock.get_balance(variant, wh) == 6
    assert stock.get_balance(variant, other) == 4
    assert _fresh(variant).stock == 10
    assert stock.journal_balance(variant.pk, wh.pk) == 6
    assert stock.journal_balance(variant.pk, other.pk) == 4


def test_transfer_insufficient(variant, wh, supplier):
    other = WarehouseFactory(seller=wh.seller)
    stock.receive(variant, wh, 1, supplier=supplier)
    with pytest.raises(stock.InsufficientStockError):
        stock.transfer(variant, wh, other, 2)


def test_adjust_creates_surplus_and_shortage(variant, wh, supplier):
    stock.receive(variant, wh, 10, supplier=supplier)
    m1 = stock.adjust(variant, wh, 7)
    assert m1.movement_type == StockMovement.ADJUSTMENT_OUT and m1.quantity == 3
    m2 = stock.adjust(variant, wh, 12)
    assert m2.movement_type == StockMovement.ADJUSTMENT and m2.quantity == 5
    assert stock.adjust(variant, wh, 12) is None
    assert _fresh(variant).stock == 12
    assert stock.journal_balance(variant.pk) == 12


def test_reserve_is_all_or_nothing(wh, supplier):
    a, b = ProductVariantFactory(), ProductVariantFactory()
    stock.receive(a, wh, 5, supplier=supplier)
    stock.receive(b, wh, 1, supplier=supplier)
    with pytest.raises(stock.InsufficientStockError):
        stock.reserve([(a, 2), (b, 2)])
    assert _fresh(a).reserved == 0 and _fresh(b).reserved == 0


def test_release_and_write_off_reserved(variant, wh, supplier):
    other = WarehouseFactory(seller=wh.seller)
    stock.receive(variant, wh, 2, supplier=supplier)
    stock.receive(variant, other, 3, supplier=supplier)
    stock.reserve([(variant, 4)])
    stock.release([(variant, 1)])
    assert _fresh(variant).reserved == 3

    movements = stock.write_off_reserved([(variant, 3)])
    v = _fresh(variant)
    assert (v.stock, v.reserved) == (2, 0)
    # сначала склад по умолчанию
    assert movements[0].warehouse_id == wh.pk and movements[0].quantity == 2
    assert stock.journal_balance(variant.pk) == 2


def test_rebuild_from_journal_fixes_cache(variant, wh, supplier):
    stock.receive(variant, wh, 4, supplier=supplier)
    ProductVariant.objects.filter(pk=variant.pk).update(stock=999)
    StockBalance.objects.filter(variant=variant).update(quantity=0)
    assert stock.rebuild_from_journal(variant) == 4
    assert _fresh(variant).stock == 4
    assert stock.get_balance(variant, wh) == 4
