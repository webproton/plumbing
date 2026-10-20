from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import CommandError, call_command

from app.apps.accounts.tests.factories import UserFactory
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import ProductFactory, ProductVariantFactory
from app.apps.warehouse.models import StockMovement
from app.apps.warehouse.tests.factories import SellerFactory, WarehouseFactory

pytestmark = pytest.mark.django_db


def seed(*args):
    call_command("seed_demo", "--force", *args, stdout=StringIO())


def test_refuses_without_force_when_debug_off():
    with pytest.raises(CommandError, match="--force"):
        call_command("seed_demo")


def test_empty_catalog_gets_demo_products_with_stock():
    admin = UserFactory(is_superuser=True)
    seed()
    variants = ProductVariant.objects.filter(code__startswith="DEMO-")
    assert variants.count() == 10
    assert all(v.available_stock == Decimal("20") for v in variants)
    assert all(v.product.seller.user == admin for v in variants)
    movement = StockMovement.objects.filter(variant__code="DEMO-01").get()
    assert movement.movement_type == StockMovement.IN
    assert movement.supplier.code == "demo"
    assert movement.price_per_unit == Decimal("2415")  # 70 % от 3450


def test_tops_up_only_out_of_stock_variants_of_this_seller_and_is_idempotent():
    warehouse = WarehouseFactory(is_default=True)
    mine = ProductVariantFactory(product=ProductFactory(seller=warehouse.seller), price=500)
    orphan = ProductVariantFactory(product=ProductFactory(seller=None), price=300)
    foreign = ProductVariantFactory(product=ProductFactory(seller=SellerFactory()), price=200)
    hidden = ProductVariantFactory(product=ProductFactory(seller=warehouse.seller), available=False)

    seed("--seller", warehouse.seller.user.email, "--qty", "5")
    seed("--seller", warehouse.seller.user.email, "--qty", "5")

    for variant, expected in ((mine, "5"), (orphan, "5"), (foreign, "0"), (hidden, "0")):
        variant.refresh_from_db()
        assert variant.stock == Decimal(expected), variant
    assert StockMovement.objects.filter(warehouse=warehouse).count() == 2
    assert not ProductVariant.objects.filter(code__startswith="DEMO-").exists()  # каталог не пуст
