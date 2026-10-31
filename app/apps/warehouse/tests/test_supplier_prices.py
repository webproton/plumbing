from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from app.apps.imports.models import ImportSource, SupplierItem
from app.apps.products.tests.factories import ProductVariantFactory
from app.apps.warehouse import stock, supplier_prices
from app.apps.warehouse.models import CurrencyRate, InventoryDocument, StockMovement, SupplierQuote
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory, WarehouseFactory

pytestmark = pytest.mark.django_db

D = Decimal


@pytest.fixture
def seller():
    return SellerFactory()


@pytest.fixture
def client(seller):
    c = APIClient()
    c.force_authenticate(seller.user)
    return c


@pytest.fixture
def variant(seller):
    return ProductVariantFactory(product__seller=seller, variant_name="Змішувач Grohe", code="GR-1", price=D("2500"))


def feed_item(seller, variant, supplier=None, *, cost, currency="UAH", price=None, available=True, name="Фід"):
    source = ImportSource.objects.create(seller=seller, name=name, kind="feed", supplier=supplier, currency=currency)
    return SupplierItem.objects.create(
        source=source,
        external_id=f"{source.pk}-{variant.pk}",
        name=variant.variant_name,
        cost=cost,
        price=price,
        currency=currency,
        available=available,
        status=SupplierItem.LINKED,
        variant=variant,
    )


def test_three_sources_best_price_and_summary(seller, variant):
    CurrencyRate.objects.create(code="USD", rate=D("41.50"))
    epicentr, aquadom, santan = SupplierFactory(name="Епіцентр"), SupplierFactory(name="Аквадом"), SupplierFactory(name="Сантан")
    variant.cost_price = D("2000")
    variant.save()

    feed_item(seller, variant, epicentr, cost=D("1900"), price=D("2600"))
    feed_item(seller, variant, None, cost=D("40"), currency="USD", name="Прайс без постачальника")  # 1660 грн
    wh = WarehouseFactory(seller=seller)
    stock.receive(variant, wh, 2, supplier=aquadom, price_per_unit=D("1750"), document_number="17")
    SupplierQuote.objects.create(seller=seller, variant=variant, supplier=santan, price=D("1500"), in_stock=False)

    offers = supplier_prices.collect_offers([variant.pk], seller)[variant.pk]
    assert [(o.kind, o.cost_uah) for o in offers] == [
        ("manual", D("1500.00")),
        ("feed", D("1660.00")),
        ("invoice", D("1750.00")),
        ("feed", D("1900.00")),
    ]
    best = [o for o in offers if o.best]
    assert len(best) == 1 and best[0].supplier_name == "Прайс без постачальника"  # у Сантану товару немає

    row = supplier_prices.summarize(variant, offers)
    assert row["suppliers"] == 4
    assert (row["min_cost"], row["max_cost"], row["spread_pct"]) == (D("1500.00"), D("1900.00"), D("26.7"))
    assert row["margin_pct"] == D("33.6")  # (2500 - 1660) / 2500
    assert row["saving"] == D("340.00")  # себестоимость 2000 против 1660
    assert offers[3].rrp_uah == D("2600.00")


def test_reversed_invoice_and_missing_feed_are_ignored(seller, variant):
    supplier = SupplierFactory()
    wh = WarehouseFactory(seller=seller)
    doc = InventoryDocument.objects.create(seller=seller, supplier=supplier, document_type="incoming")
    stock.receive(variant, wh, 1, supplier=supplier, price_per_unit=D("900"), inventory_document=doc)
    StockMovement.objects.create(
        variant=variant,
        seller=seller,
        warehouse=wh,
        movement_type=StockMovement.IN_REVERSAL,
        quantity=1,
        inventory_document=doc,
    )
    item = feed_item(seller, variant, supplier, cost=D("950"))
    item.missing = True
    item.save()
    assert supplier_prices.collect_offers([variant.pk], seller) == {}
    assert supplier_prices.supplier_keys(seller) == {}


def test_api_list_filters_and_seller_isolation(client, seller, variant):
    a, b = SupplierFactory(), SupplierFactory()
    feed_item(seller, variant, a, cost=D("1000"))
    SupplierQuote.objects.create(seller=seller, variant=variant, supplier=b, price=D("1200"))
    single = ProductVariantFactory(product__seller=seller, variant_name="Труба PPR 20", price=D("50"))
    feed_item(seller, single, a, cost=D("30"))
    other = SellerFactory()
    alien = ProductVariantFactory(product__seller=other, variant_name="Чужий товар")
    feed_item(other, alien, a, cost=D("1"))

    url = reverse("warehouse:supplier_prices")
    data = client.get(url).json()
    assert data["count"] == 2
    assert data["results"][0]["name"] == "Змішувач Grohe"  # найбільша різниця — першою
    assert data["results"][0]["spread_pct"] == 20.0

    assert [r["name"] for r in client.get(url, {"multi": "1"}).json()["results"]] == ["Змішувач Grohe"]
    assert [r["name"] for r in client.get(url, {"search": "ppr"}).json()["results"]] == ["Труба PPR 20"]

    detail = client.get(reverse("warehouse:supplier_price_detail", args=[variant.pk])).json()
    assert detail["best"]["cost_uah"] == 1000.0 and len(detail["offers"]) == 2
    assert client.get(reverse("warehouse:supplier_price_detail", args=[alien.pk])).status_code == 404


def test_api_quote_upsert_validation_and_delete(client, seller, variant):
    supplier = SupplierFactory()
    url = reverse("warehouse:supplier-quote-list")
    payload = {"variant": variant.pk, "supplier": supplier.pk, "price": "1450", "note": "прайс від 20.10"}

    created = client.post(url, payload, format="json")
    assert created.status_code == 201, created.content
    updated = client.post(url, {**payload, "price": "1400", "currency": "UAH", "in_stock": True}, format="json")
    assert updated.status_code == 200 and updated.json()["id"] == created.json()["id"]
    quote = SupplierQuote.objects.get()
    assert (quote.price, quote.in_stock, quote.seller) == (D("1400"), True, seller)

    assert client.post(url, {**payload, "price": "0"}, format="json").status_code == 400
    assert client.post(url, {**payload, "currency": "PLN"}, format="json").status_code == 400
    alien = ProductVariantFactory(product__seller=SellerFactory())
    assert client.post(url, {**payload, "variant": alien.pk}, format="json").status_code == 404

    assert client.get(url, {"variant": variant.pk}).json()["count"] == 1
    assert client.delete(reverse("warehouse:supplier-quote-detail", args=[quote.pk])).status_code == 204
    assert not SupplierQuote.objects.exists()


def test_other_seller_cannot_touch_quote(seller, variant):
    quote = SupplierQuote.objects.create(seller=seller, variant=variant, supplier=SupplierFactory(), price=D("10"))
    stranger = APIClient()
    stranger.force_authenticate(SellerFactory().user)
    assert stranger.delete(reverse("warehouse:supplier-quote-detail", args=[quote.pk])).status_code == 404


@pytest.mark.django_db
def test_currency_rates_are_editable_in_admin(client):
    from django.contrib.auth import get_user_model


    admin_user = get_user_model().objects.create_superuser("rates@example.com", "Str0ngPass!")
    client.force_login(admin_user)
    assert client.get("/admin/warehouse/currencyrate/").status_code == 200
    response = client.post("/admin/warehouse/currencyrate/add/", {"code": "USD", "rate": "41.20"})
    assert response.status_code == 302
    assert CurrencyRate.objects.get(code="USD").rate == Decimal("41.20")
