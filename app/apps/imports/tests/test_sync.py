import json
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from app.apps.accounts.tests.factories import UserFactory
from app.apps.imports import services, tasks
from app.apps.imports.connectors import web
from app.apps.imports.models import ImportRun, ImportSource, SupplierItem
from app.apps.imports.serializers import ImportSourceSerializer
from app.apps.products.models import ProductVariant
from app.apps.products.tests.factories import CategoryFactory, ProductVariantFactory
from app.apps.warehouse import stock
from app.apps.warehouse.models import CurrencyRate
from app.apps.warehouse.supplier_prices import collect_offers
from app.apps.warehouse.tests.factories import SellerFactory, SupplierFactory

pytestmark = pytest.mark.django_db


def yml(offers: str, currency="UAH") -> bytes:
    return f"""<yml_catalog><shop><currencies><currency id="{currency}"/></currencies>
    <categories><category id="1">Змішувачі</category></categories><offers>{offers}</offers></shop></yml_catalog>""".encode()


def offer(oid, name, price, *, sku="", barcode="", cost="", qty="", available="true", currency="UAH", old=""):
    return (
        f'<offer id="{oid}" available="{available}"><name>{name}</name><price>{price}</price>'
        f"<currencyId>{currency}</currencyId><categoryId>1</categoryId>"
        + (f"<vendorCode>{sku}</vendorCode>" if sku else "")
        + (f"<barcode>{barcode}</barcode>" if barcode else "")
        + (f"<price_opt>{cost}</price_opt>" if cost else "")
        + (f"<oldprice>{old}</oldprice>" if old else "")
        + (f"<quantity_in_stock>{qty}</quantity_in_stock>" if qty != "" else "")
        + "<picture>https://cdn.example.com/p.jpg</picture></offer>"
    )


def make_source(seller, content: bytes, **fields):
    source = ImportSource(seller=seller, name="Фід", kind="feed", **fields)
    source.file.save("feed.yml", SimpleUploadedFile("feed.yml", content), save=False)
    source.save()
    return source


def replace_file(source, content: bytes):
    source.file.delete(save=False)
    source.file.save("feed.yml", SimpleUploadedFile("feed.yml", content))


def test_sync_creates_items_links_and_updates_prices(seller):
    by_barcode = ProductVariantFactory(product__seller=seller, barcode="4005176000001", price=Decimal("1"))
    by_sku = ProductVariantFactory(product__seller=seller, code="TR-20", price=Decimal("1"))
    alien = ProductVariantFactory(product__seller=SellerFactory(), code="ALIEN", price=Decimal("1"))
    feed = yml(
        offer("A", "Змішувач", "2499", barcode="4005176000001", old="2999")
        + offer("B", "Труба", "55.4", sku="TR-20")
        + offer("C", "Чужий", "10", sku="ALIEN")
        + offer("D", "Новий", "100")
    )
    source = make_source(seller, feed, price_rounding=Decimal("1"))
    run = services.sync_source(source)

    assert run.status == ImportRun.DONE, run.error
    assert run.stats["new"] == 4 and run.stats["linked_auto"] == 2 and run.stats["price_changed"] == 2
    by_barcode.refresh_from_db()
    by_sku.refresh_from_db()
    alien.refresh_from_db()
    assert (by_barcode.price, by_barcode.original_price, by_barcode.discount) == (
        Decimal("2499.00"),
        Decimal("2999.00"),
        17,
    )
    assert by_sku.price == Decimal("55.00")  # округление до гривны
    assert alien.price == Decimal("1.00")  # товары другого продавца не трогаем
    assert SupplierItem.objects.get(source=source, external_id="C").status == SupplierItem.NEW
    source.refresh_from_db()
    assert source.last_status == "ok" and source.last_sync_at is not None


def test_markup_mode_and_currency(seller):
    CurrencyRate.objects.create(code="USD", rate=Decimal("41.50"))
    variant = ProductVariantFactory(product__seller=seller, code="U-1", price=Decimal("1"))
    feed = yml(offer("U", "Бойлер", "200", sku="U-1", cost="100", currency="USD"))
    source = make_source(seller, feed, price_mode="markup", markup_percent=Decimal("20"), price_rounding=Decimal("10"))
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.price == Decimal("4980.00")  # 100 × 1.2 × 41.5 = 4980
    assert variant.cost_price == Decimal("4150.0000")

    CurrencyRate.objects.all().delete()  # нет курса — цену не трогаем
    ProductVariant.objects.filter(pk=variant.pk).update(price=Decimal("1"))
    replace_file(source, feed.replace("Бойлер".encode(), "Бойлер 2".encode()))
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.price == Decimal("1.00")


def test_partner_discount_from_rrp_gives_cost(seller):
    # O&L отдаёт только РРЦ: закупка = РРЦ − скидка партнёра, у бренда может быть своя
    koer = ProductVariantFactory(product__seller=seller, code="KP2668", price=Decimal("1"))
    grohe = ProductVariantFactory(product__seller=seller, code="GR-1", price=Decimal("1"))
    priced = ProductVariantFactory(product__seller=seller, code="P-1", price=Decimal("1"))
    feed = yml(
        offer("K", "Насосна станція Koer", "6240", sku="KP2668").replace("</offer>", "<vendor>KOER</vendor></offer>")
        + offer("G", "Змішувач Grohe", "1000", sku="GR-1").replace("</offer>", "<vendor>Grohe</vendor></offer>")
        + offer("P", "Із закупкою в прайсі", "1000", sku="P-1", cost="700")
    )
    source = make_source(
        seller, feed, partner_discount_percent=Decimal("17.7"), partner_discount_brands={" grohe ": 25}
    )
    services.sync_source(source)
    for variant in (koer, grohe, priced):
        variant.refresh_from_db()
    assert (koer.price, koer.cost_price) == (Decimal("6240.00"), Decimal("5135.5200"))  # 6240 − 17,7 %
    assert grohe.cost_price == Decimal("750.0000")  # своя скидка бренда, регистр и пробелы не важны
    assert priced.cost_price == Decimal("700.0000")  # закупка из прайса важнее оценки

    best = collect_offers([koer.pk], seller)[koer.pk][0]
    assert best.cost_uah == Decimal("5135.52") and best.ref == "Фід: РРЦ − 17.7 %"


def test_partner_discount_validation():
    serializer = ImportSourceSerializer()
    assert serializer.validate_partner_discount_brands({" KOER ": "17,7", "Grohe": 25}) == {"KOER": 17.7, "Grohe": 25.0}
    for bad in ({"KOER": "?"}, {"KOER": "NaN"}, {"KOER": 100}, {" ": 10}, ["KOER"]):
        with pytest.raises(ValidationError):
            serializer.validate_partner_discount_brands(bad)
    with pytest.raises(ValidationError):
        serializer.validate_partner_discount_percent(Decimal("100"))


def test_second_sync_detects_changes_and_missing(seller):
    source = make_source(seller, yml(offer("A", "Один", "10") + offer("B", "Два", "20")))
    services.sync_source(source)
    replace_file(source, yml(offer("A", "Один", "11") + offer("C", "Три", "30")))
    run = services.sync_source(source)
    assert (run.stats["new"], run.stats["changed"], run.stats["unchanged"], run.stats["missing"]) == (1, 1, 0, 1)
    assert SupplierItem.objects.get(external_id="B").missing is True

    replace_file(source, yml(offer("A", "Один", "11") + offer("B", "Два", "20") + offer("C", "Три", "30")))
    run = services.sync_source(source)
    assert run.stats["unchanged"] == 3 and not SupplierItem.objects.filter(missing=True).exists()


def test_hide_and_show_by_supplier_availability(seller):
    from app.apps.warehouse.tests.factories import WarehouseFactory

    variant = ProductVariantFactory(product__seller=seller, code="H-1", available=True)
    source = make_source(
        seller, yml(offer("H", "Кран", "10", sku="H-1", available="false", qty="0")), hide_when_unavailable=True
    )
    run = services.sync_source(source)
    variant.refresh_from_db()
    assert variant.available is False and run.stats["hidden"] == 1

    replace_file(source, yml(offer("H", "Кран", "10", sku="H-1", qty="5")))
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.available is True

    # скрытый вручную товар синхронизация не показывает
    ProductVariant.objects.filter(pk=variant.pk).update(available=False)
    replace_file(source, yml(offer("H", "Кран", "11", sku="H-1", qty="6")))
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.available is False

    # есть свой остаток — не скрываем, даже если у поставщика нет
    ProductVariant.objects.filter(pk=variant.pk).update(available=True)
    stock.receive(variant, WarehouseFactory(seller=seller), 2, supplier=SupplierFactory())
    replace_file(source, yml(offer("H", "Кран", "11", sku="H-1", available="false", qty="0")))
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.available is True


def test_sync_errors_are_recorded(seller):
    source = make_source(seller, b"<yml_catalog><shop><offers></offers></shop></yml_catalog>")
    run = services.sync_source(source)
    assert run.status == ImportRun.FAILED and run.error
    source.refresh_from_db()
    assert source.last_status == "error" and source.last_error

    web_source = ImportSource.objects.create(seller=seller, name="B2B", kind="web", adapter="unknown", auth_login="me")
    assert services.sync_source(web_source).status == ImportRun.FAILED


def test_publish_link_ignore(seller):
    category = CategoryFactory()
    source = make_source(
        seller, yml(offer("A", "Новий змішувач", "1000", sku="NEW-1", cost="600") + offer("B", "Інше", "5"))
    )
    services.sync_source(source)
    a, b = SupplierItem.objects.get(external_id="A"), SupplierItem.objects.get(external_id="B")

    result = services.publish_items(source, [a.pk], category=category)
    assert len(result["created"]) == 1
    a.refresh_from_db()
    variant = a.variant
    assert a.status == SupplierItem.LINKED and a.match_method == "created"
    assert variant.code == "NEW-1" and variant.price == Decimal("1000.00") and variant.cost_price == Decimal("600.0000")
    assert variant.available is False and variant.product.seller == seller and variant.product.category == category

    mine = ProductVariantFactory(product__seller=seller)
    alien = ProductVariantFactory(product__seller=SellerFactory())
    with pytest.raises(services.ImportActionError):
        services.link_item(b, alien.pk)
    with pytest.raises(services.ImportActionError):
        services.link_item(b, variant.pk)  # уже связан с позицией A
    services.link_item(b, mine.pk)
    mine.refresh_from_db()
    assert mine.price == Decimal("5.00")

    assert services.set_status(source, [b.pk], SupplierItem.NEW) == 1
    assert services.set_status(source, [b.pk], SupplierItem.IGNORED) == 1
    b.refresh_from_db()
    assert b.status == SupplierItem.IGNORED and b.variant is None


def test_api_flow_and_isolation(client, seller, photo_requests):
    feed = SimpleUploadedFile("feed.yml", yml(offer("A", "Змішувач", "100", sku="S-1")))
    resp = client.post(
        reverse("imports:source-list"),
        {
            "name": "Постачальник",
            "kind": "feed",
            "file": feed,
            "secret": "top-secret",
            "auth_type": "basic",
            "auth_login": "u",
            # так отправляет форма кабинета, когда приложен файл: JSON-поля строками
            "field_map": json.dumps({"sku": "vendorCode"}),
            "options": json.dumps({"encoding": "utf-8"}),
            "publish_new": "false",
            "category": "",
        },
        format="multipart",
    )
    assert resp.status_code == 201, resp.json()
    data = resp.json()
    assert data["field_map"] == {"sku": "vendorCode"} and data["options"] == {"encoding": "utf-8"}
    assert data["category"] is None and data["publish_new"] is False
    assert data["has_secret"] is True and data["has_file"] is True and "secret" not in data
    source = ImportSource.objects.get(pk=data["id"])
    assert "top-secret" not in source.secret_encrypted and source.secret == "top-secret"

    resp = client.post(reverse("imports:source-sync", args=[source.pk]))
    assert resp.status_code == 202 and resp.json()["status"] == "done"
    listing = client.get(reverse("imports:source-list")).json()["results"][0]
    assert listing["counts"]["total"] == 1 and listing["last_status"] == "ok"

    items = client.get(reverse("imports:source-items", args=[source.pk]), {"status": "new"}).json()
    item = items["results"][0]
    assert item["our_price"] == "100.00" and item["photo"] == "https://cdn.example.com/p.jpg"
    cats = client.get(reverse("imports:source-categories", args=[source.pk])).json()
    assert cats == [{"category_name": "Змішувачі", "total": 1, "new": 1}]

    resp = client.post(
        reverse("imports:source-publish", args=[source.pk]), {"ids": [item["id"]], "visible": True}, format="json"
    )
    assert resp.json() == {"created": 1, "linked": 0, "skipped": 0, "photos_queued": 1}
    assert photo_requests == ["https://cdn.example.com/p.jpg"]
    assert ProductVariant.objects.get(code="S-1").available is True

    # пустой secret при обновлении не стирает пароль
    client.patch(
        reverse("imports:source-detail", args=[source.pk]), {"secret": "", "markup_percent": "15"}, format="json"
    )
    source.refresh_from_db()
    assert source.secret == "top-secret" and source.markup_percent == Decimal("15")

    other = APIClient()
    other.force_authenticate(SellerFactory().user)
    assert other.get(reverse("imports:source-detail", args=[source.pk])).status_code == 404
    assert other.post(reverse("imports:source-sync", args=[source.pk])).status_code == 404
    buyer = APIClient()
    buyer.force_authenticate(UserFactory())
    assert buyer.get(reverse("imports:source-list")).status_code == 403


def test_source_validation(client):
    url = reverse("imports:source-list")
    assert client.post(url, {"name": "X", "kind": "feed"}, format="json").status_code == 400
    assert client.post(url, {"name": "X", "kind": "feed", "url": "ftp://x/y"}, format="json").status_code == 400
    assert client.post(url, {"name": "X", "kind": "web", "adapter": "nope"}, format="json").status_code == 400
    bad_interval = {"name": "X", "kind": "feed", "url": "https://x.test/f.xml", "sync_interval_minutes": 5}
    assert client.post(url, bad_interval, format="json").status_code == 400
    ok = {
        "name": "X",
        "kind": "web",
        "adapter": "form_login",
        "auth_login": "me",
        "options": {"login_url": "https://b2b.test/login"},
    }
    assert client.post(url, ok, format="json").status_code == 201
    adapters = client.get(reverse("imports:adapters")).json()
    assert [a["code"] for a in adapters] == ["form_login"] and "export_url" in adapters[0]["options"]


def test_form_login_adapter(seller, monkeypatch):
    calls = []

    class Result:
        def __init__(self, body, url="https://b2b.test/x"):
            self.content, self.url = body, url

    def fake_fetch(url, *, session=None, method="GET", data=None, **kwargs):
        calls.append((method, url, data))
        if url.endswith("/login") and method == "GET":
            return Result(b'<form><input type="hidden" name="_token" value="abc&amp;1"><input name="password"></form>')
        if url.endswith("/login"):
            ok = data.get("password") == "pw"
            return Result(b"<a>Exit</a>" if ok else b'<input name="password">')
        return Result(yml(offer("W", "З кабінету", "77", sku="W-1")), url="https://b2b.test/price.yml")

    monkeypatch.setattr(web, "fetch", fake_fetch)
    source = ImportSource(
        seller=seller,
        name="B2B",
        kind="web",
        adapter="form_login",
        auth_login="shop@example.com",
        options={"login_url": "https://b2b.test/login", "csrf_field": "_token", "export_url": "/price.yml"},
    )
    source.secret = "pw"
    source.save()
    run = services.sync_source(source)
    assert run.status == ImportRun.DONE, run.error
    assert calls[1] == (
        "POST",
        "https://b2b.test/login",
        {"login": "shop@example.com", "password": "pw", "_token": "abc&1"},
    )
    assert calls[2][1] == "https://b2b.test/price.yml"

    source.secret = "wrong"
    source.save()
    run = services.sync_source(source)
    assert run.status == ImportRun.FAILED and "логин" in run.error


def test_api_connector_pagination(seller, monkeypatch):
    from app.apps.imports.connectors import api

    pages = {
        1: b'{"items": [{"sku": "P1", "name": "One", "price": 1}]}',
        2: b'{"items": [{"sku": "P2", "name": "Two", "price": 2}]}',
        3: b'{"items": []}',
    }
    seen = []

    class Result:
        def __init__(self, content):
            self.content = content

    def fake_fetch(url, params=None, headers=None, **kwargs):
        seen.append((params, headers.get("Authorization")))
        return Result(pages[params["page"]])

    monkeypatch.setattr(api, "fetch", fake_fetch)
    source = ImportSource(
        seller=seller, name="API", kind="api", url="https://api.test/products", auth_type="bearer",
        options={"page_param": "page", "items_path": "items"},
    )  # fmt: skip
    source.secret = "tok"
    source.save()
    run = services.sync_source(source)
    assert run.status == ImportRun.DONE and run.stats["total"] == 2
    assert [p for p, _a in seen] == [{"page": 1}, {"page": 2}, {"page": 3}]
    assert seen[0][1] == "Bearer tok"


def test_beat_schedules_due_sources_and_lock(seller, monkeypatch):
    due = make_source(seller, yml(offer("A", "Один", "10")), sync_interval_minutes=60)
    make_source(seller, yml(offer("A", "Один", "10")), sync_interval_minutes=0)
    later = make_source(seller, yml(offer("A", "Один", "10")), sync_interval_minutes=60)
    ImportSource.objects.filter(pk=later.pk).update(next_sync_at=timezone.now() + timezone.timedelta(hours=1))
    synced = []
    monkeypatch.setattr(tasks.services, "sync_source", lambda source, run=None: synced.append(source.pk))
    tasks.sync_due_sources()
    assert synced == [due.pk]
    due.refresh_from_db()
    assert due.next_sync_at > timezone.now()

    from django.core.cache import cache

    cache.add(f"imports:sync:{due.pk}", 1)
    run = ImportRun.objects.create(kind="sync", seller=seller, source=due)
    tasks.sync_source_task(due.pk, run.pk)
    run.refresh_from_db()
    assert run.status == ImportRun.FAILED and synced == [due.pk]


def test_stale_runs_are_failed(seller):
    run = ImportRun.objects.create(kind="sync", seller=seller, status=ImportRun.RUNNING)
    ImportRun.objects.filter(pk=run.pk).update(created_at=timezone.now() - timezone.timedelta(hours=3))
    assert services.fail_stale_runs() == 1
    run.refresh_from_db()
    assert run.status == ImportRun.FAILED


def test_cost_in_its_own_currency_and_rrp_price(seller):
    """Секвоя: продаём по РРЦ (грн), закупка — опт в $ по курсу (из прайса — 46.55), а не «0,26 грн»."""
    from app.apps.imports.tests.test_formats import SEQUOIA

    CurrencyRate.objects.create(code="USD", rate=Decimal("40"))
    variant = ProductVariantFactory(product__seller=seller, code="1003390", price=Decimal("1"))
    source = make_source(seller, SEQUOIA.encode(), price_rounding=Decimal("0.01"))
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.price == Decimal("15.60")  # РРЦ
    assert variant.cost_price == Decimal("12.1030")  # 0.26 $ × 46.55 — курс из прайса важнее общего (40)
    item = SupplierItem.objects.get(source=source, external_id__contains="1003390")
    assert (item.cost_currency, item.photos) == ("USD", ["https://b2b.example.com//gallery/product_gallery/a.webp"])

    # повторная загрузка (позиция уже есть — обновляется, а не создаётся): валюта закупки не теряется
    SupplierItem.objects.filter(pk=item.pk).update(cost_currency="")
    replace_file(source, SEQUOIA.replace("0.26", "0.30").encode())
    services.sync_source(source)
    item.refresh_from_db()
    variant.refresh_from_db()
    assert (item.cost, item.cost_currency, variant.cost_price) == (Decimal("0.3000"), "USD", Decimal("13.9650"))


def test_supplier_rate_from_feed_and_manual_override(seller):
    """Курс у поставщика свой: Секвоя пишет Rate="46.55" прямо в прайсе; вручную в джерелі — важнее; общий — последним."""
    from app.apps.imports.tests.test_formats import SEQUOIA

    CurrencyRate.objects.create(code="USD", rate=Decimal("40"))
    variant = ProductVariantFactory(product__seller=seller, code="1003390", price=Decimal("1"))
    source = make_source(seller, SEQUOIA.encode(), price_rounding=Decimal("0.01"))
    run = services.sync_source(source)
    variant.refresh_from_db()
    source.refresh_from_db()
    assert run.stats["rates"] == {"USD": "46.55"} and source.options["feed_rates"] == {"USD": "46.55"}
    assert variant.cost_price == Decimal("12.1030")  # 0.26 $ × 46.55 (курс поставщика, не общий 40)

    source.currency_rates = {"USD": 45}
    source.save()
    replace_file(source, SEQUOIA.replace("0.26", "0.30").encode())
    services.sync_source(source)
    variant.refresh_from_db()
    assert variant.cost_price == Decimal("13.5000")  # 0.30 × 45 — ручной курс важнее курса из прайса

    serializer = ImportSourceSerializer(source, data={"options": {"items_tag": "Product"}}, partial=True)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data["options"] == {"items_tag": "Product", "feed_rates": {"USD": "46.55"}}
    bad = ImportSourceSerializer(source, data={"currency_rates": {"долар": "x"}}, partial=True)
    assert not bad.is_valid() and "currency_rates" in bad.errors


def test_factory_barcodes_learned_from_price_list(seller):
    """Прайс со штрихкодами: товар связался по артикулу — заводской штрихкод становится доп. штрихкодом для сканера."""
    from app.apps.warehouse.inventory.barcode_scanner import find_variant_by_code
    from app.apps.warehouse.models import ProductBarcode

    variant = ProductVariantFactory(product__seller=seller, code="KR2675", barcode="2048179886469")
    taken = ProductVariantFactory(product__seller=seller, code="OTHER", barcode="4820000000028")
    feed = yml(
        offer("A", "Група безпеки 1", "1256", sku="KR2675", barcode="4820123456789")
        + offer("B", "Інший товар", "10", sku="NEW-1", barcode="4820000000028")  # код уже есть у товара — дубль не нужен
    )
    run = services.sync_source(make_source(seller, feed))
    assert run.status == ImportRun.DONE, run.error
    assert run.stats["barcodes_learned"] == 1
    assert find_variant_by_code("4820123456789") == variant
    assert find_variant_by_code("2048179886469") == variant  # внутренний номер для этикеток остаётся
    assert not ProductBarcode.objects.filter(code="4820000000028").exists() and taken.barcode == "4820000000028"


def test_one_product_two_suppliers_main_offer(seller):
    """Насос у двух поставщиков: цена — от того, у кого есть и дешевле закупка, в любом порядке синхронизации;
    закончился у него — цена от второго; скрываем, только когда нет ни у кого."""
    variant = ProductVariantFactory(product__seller=seller, code="PUMP-1", price=Decimal("1"), available=True)
    a = make_source(seller, yml(offer("A1", "Насос", "150", sku="PUMP-1", cost="100", qty="5")),
                    price_rounding=Decimal("0.01"), hide_when_unavailable=True)
    b = make_source(seller, yml(offer("B1", "Насос", "140", sku="PUMP-1", cost="90", qty="3")),
                    price_rounding=Decimal("0.01"), hide_when_unavailable=True)
    for source in (b, a):  # B (дешевле) синхронизирован раньше — A не перебивает его цену
        services.sync_source(source)
    variant.refresh_from_db()
    assert (variant.price, variant.cost_price) == (Decimal("140.00"), Decimal("90.0000"))

    replace_file(b, yml(offer("B1", "Насос", "140", sku="PUMP-1", cost="90", qty="0", available="false")))
    services.sync_source(b)  # у B закончился → главный A, хотя синхронизировался B
    variant.refresh_from_db()
    assert (variant.price, variant.cost_price, variant.available) == (Decimal("150.00"), Decimal("100.0000"), True)

    replace_file(a, yml(offer("A1", "Насос", "150", sku="PUMP-1", cost="100", qty="0", available="false")))
    services.sync_source(a)  # нет ни у кого → скрыт
    variant.refresh_from_db()
    assert variant.available is False
    replace_file(b, yml(offer("B1", "Насос", "140", sku="PUMP-1", cost="90", qty="2")))
    services.sync_source(b)  # снова есть у B → показан, цена B
    variant.refresh_from_db()
    assert (variant.available, variant.price) == (True, Decimal("140.00"))
