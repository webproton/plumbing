"""Продажа «под заказ»: своего товара нет — продаём с остатка поставщика, склад при этом не трогаем."""

from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from app.apps.imports import services as imports
from app.apps.imports.models import ImportSource, SupplierItem
from app.apps.orders import services
from app.apps.orders.models import Order
from app.apps.orders.tests.factories import stock_up
from app.apps.orders.tests.test_order_flow import ORDER_URL, _cart, _payload, _variant
from app.apps.products.models import Product, ProductVariant
from app.apps.warehouse import stock
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory

pytestmark = pytest.mark.django_db


def _offer(oid, sku, *, qty="", available="true"):
    return (
        f'<offer id="{oid}" available="{available}"><name>Товар {oid}</name><price>100</price>'
        f"<vendorCode>{sku}</vendorCode>" + (f"<stock_quantity>{qty}</stock_quantity>" if qty != "" else "") + "</offer>"
    )


def _feed_source(seller, offers, **fields):
    content = f"<yml_catalog><shop><offers>{offers}</offers></shop></yml_catalog>".encode()
    source = ImportSource(seller=seller, name="O&L", kind="feed", supplier=SupplierFactory(name="O&L"), **fields)
    source.file.save("feed.yml", SimpleUploadedFile("feed.yml", content), save=False)
    source.save()
    imports.sync_source(source)
    return source


def _from_supplier(qty="7", available="true", sku="OL-1", **fields):
    """Вариант продавца без своего остатка, связанный с позицией фида по артикулу."""
    variant = _variant(stock_qty=0)
    seller = SellerFactory()
    ProductVariant.objects.filter(pk=variant.pk).update(code=sku)
    Product.objects.filter(pk=variant.product_id).update(seller=seller)
    _feed_source(seller, _offer("1", sku, qty=qty, available=available), **fields)
    return ProductVariant.objects.get(pk=variant.pk)


def test_supplier_stock_is_cached_apart_from_own_stock():
    variant = _from_supplier(qty="7", order_days=2)
    assert (variant.stock, variant.supplier_qty, variant.supplier_days) == (0, Decimal("7.000"), 2)
    assert variant.available_stock == 0 and variant.orderable_qty == 7  # склад пуст, заказать можно 7

    data = APIClient().get(reverse("products:product-detail", args=[variant.product.slug])).json()
    v = data["variants"][0]
    assert (v["in_stock"], v["on_order"], v["on_order_days"], Decimal(v["orderable_qty"])) == (False, True, 2, 7)


def test_unavailable_at_supplier_is_not_orderable():
    # «нет в наличии» важнее количества: O&L пишет 100 и у отсутствующих
    assert _from_supplier(qty="100", available="false").supplier_qty is None


def test_unknown_quantity_and_switching_off():
    variant = _from_supplier(qty="")  # количества в фиде нет, но «есть»
    assert variant.supplier_qty == imports.UNKNOWN_QTY

    source = ImportSource.objects.get(items__variant=variant)
    source.sell_on_order = False
    source.save()
    imports.refresh_supplier_stock(imports.source_variant_ids(source))
    assert ProductVariant.objects.get(pk=variant.pk).supplier_qty is None

    imports.set_status(source, source.items.values_list("pk", flat=True), SupplierItem.NEW)  # отвязали
    source.sell_on_order = True
    source.save()
    imports.refresh_supplier_stock([variant.pk])
    assert ProductVariant.objects.get(pk=variant.pk).supplier_qty is None


def test_order_on_order_line_without_reserve_then_ship_after_receipt():
    client = APIClient()
    own = _variant(stock_qty=5)
    ordered = _from_supplier(qty="7")
    resp = client.post(reverse(ORDER_URL), _payload(_cart(items=[(own, 2), (ordered, 3)])), format="json")
    assert resp.status_code == 201, resp.json()

    order = Order.objects.get(pk=resp.json()["id"])
    lines = {i.variant_id: i for i in order.items.select_related("supplier")}
    assert order.stock_state == Order.STOCK_STATE.reserved
    assert not lines[own.pk].on_order and lines[ordered.pk].on_order and lines[ordered.pk].supplier.name == "O&L"
    assert ProductVariant.objects.get(pk=own.pk).reserved == 2
    assert ProductVariant.objects.get(pk=ordered.pk).reserved == 0  # своего нет — резервировать нечего

    with pytest.raises(ValidationError):  # от поставщика ещё не пришло
        services.change_status(order, Order.STATUS.completed)
    assert ProductVariant.objects.get(pk=own.pk).reserved == 2  # всё или ничего

    stock_up(ordered, 3)  # пришла накладная
    services.change_status(order, Order.STATUS.completed)
    assert (ProductVariant.objects.get(pk=own.pk).stock, ProductVariant.objects.get(pk=ordered.pk).stock) == (3, 0)
    assert stock.journal_balance(ordered.pk) == 0


def test_cancel_releases_only_own_lines_and_all_on_order_has_nothing_to_reserve():
    client = APIClient()
    ordered = _from_supplier(qty="7")
    resp = client.post(reverse(ORDER_URL), _payload(_cart(items=[(ordered, 7)])), format="json")
    order = Order.objects.get(pk=resp.json()["id"])
    assert order.stock_state == Order.STOCK_STATE.none and order.items.get().on_order

    services.change_status(order, Order.STATUS.canceled)
    assert ProductVariant.objects.get(pk=ordered.pk).reserved == 0


def test_more_than_supplier_has_is_rejected():
    ordered = _from_supplier(qty="2")
    resp = APIClient().post(reverse(ORDER_URL), _payload(_cart(items=[(ordered, 3)])), format="json")
    assert resp.status_code == 400 and resp.json()["code"] == "insufficient_stock"
