"""Сайт поставщика на OpenCart без выгрузки: обход разделов → товары с фото, описанием, характеристиками."""

import json
from types import SimpleNamespace

import pytest

from app.apps.imports.connectors import get_connector
from app.apps.imports.connectors.opencart import parse_product
from app.apps.imports.models import ImportSource

pytestmark = pytest.mark.django_db

ROOT = "https://mebli.example.com/"


def _product_page(name, code, price, images):
    ld = {
        "@context": "https://schema.org", "@type": "Product", "name": name, "image": images,
        "description": "Шафа з двома дверцятами", "brand": {"@type": "Brand", "name": "Світ меблів"},
        "offers": {"@type": "Offer", "price": price, "priceCurrency": "UAH", "availability": "https://schema.org/InStock"},
    }
    crumbs = {"@type": "BreadcrumbList", "itemListElement": [
        {"position": 1, "item": {"name": "Головна"}}, {"position": 2, "item": {"name": "Спальні"}},
        {"position": 3, "item": {"name": "Шафи"}}, {"position": 4, "item": {"name": name}}]}
    return f"""<html><script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>
    <script type="application/ld+json">{json.dumps(crumbs, ensure_ascii=False)}</script>
    <span>Код товару:</span> {code}
    <a href="{ROOT}image/cache/catalog/mebli/{code}-2-300x300.jpg" data-zoom-image="{ROOT}image/catalog/mebli/{code}-2.jpg">x</a>
    <table><tr><td>Ширина, мм</td><td>1200</td></tr><tr><td>Матеріал</td><td>ДСП</td></tr></table></html>"""


PAGES = {
    ROOT: f'<a href="{ROOT}spalni">Спальні</a> <a href="{ROOT}index.php?route=checkout/cart">Кошик</a>',
    f"{ROOT}spalni": f'<a href="{ROOT}shafa-1">Шафа</a> <a href="{ROOT}spalni?page=2">2</a> <a href="{ROOT}spalni?sort=p.price">sort</a>',
    f"{ROOT}spalni?page=2": f'<a href="{ROOT}komod-1">Комод</a>',
    f"{ROOT}shafa-1": _product_page("Шафа Б'янко 3Д", "bianco-3d", "7843", [f"{ROOT}image/catalog/mebli/bianco-3d.jpg"]),
    f"{ROOT}komod-1": _product_page("Комод Б'янко", "bianco-komod", "5120", f"{ROOT}image/catalog/mebli/komod.jpg"),
}


def test_parse_product_page():
    data = parse_product(PAGES[f"{ROOT}shafa-1"], f"{ROOT}shafa-1")
    values, params = data["values"], data["params"]
    assert values["name"] == "Шафа Б'янко 3Д" and values["sku"] == "bianco-3d" and values["price"] == "7843"
    assert values["photos"] == [f"{ROOT}image/catalog/mebli/bianco-3d.jpg", f"{ROOT}image/catalog/mebli/bianco-3d-2.jpg"]
    assert values["category"] == "Спальні / Шафи" and values["brand"] == "Світ меблів" and values["available"] is True
    assert params == {"Ширина, мм": "1200", "Матеріал": "ДСП"}
    assert parse_product(PAGES[ROOT], ROOT) is None  # не товар


def test_crawls_sections_and_pages_politely(monkeypatch, seller):
    source = ImportSource.objects.create(seller=seller, name="Світ меблів", kind="web", adapter="opencart_site", url=ROOT,
                                         options={"delay_seconds": 0})
    opened = []

    def fake_get(self, url, **kw):
        opened.append(url)
        return SimpleNamespace(content=PAGES.get(url, "<html></html>").encode())

    monkeypatch.setattr("app.apps.imports.connectors.web.SiteAdapter.get", fake_get)
    catalog = get_connector(source).fetch()
    assert sorted(i.name for i in catalog.items) == ["Комод Б'янко", "Шафа Б'янко 3Д"]
    assert not any("route=" in u or "sort=" in u for u in opened)  # корзину и сортировки не открываем
