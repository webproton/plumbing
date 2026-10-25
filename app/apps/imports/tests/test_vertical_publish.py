"""Публикация из фида в корень направления: товары раскладываются по подкатегориям, характеристики сохраняются."""
import pytest

from app.apps.imports import services
from app.apps.imports.models import SupplierItem
from app.apps.imports.tests.test_sync import make_source
from app.apps.products.catalog.services import ensure_taxonomy
from app.apps.products.catalog.taxonomy import VERTICALS
from app.apps.products.models import Category

pytestmark = pytest.mark.django_db


def feed(*offers: str) -> bytes:
    return (
        '<yml_catalog><shop><currencies><currency id="UAH"/></currencies>'
        '<categories><category id="1">Сантехніка</category></categories><offers>'
        + "".join(offers)
        + "</offers></shop></yml_catalog>"
    ).encode()


def offer(oid, name, price, **params):
    tags = "".join(f'<param name="{k}">{v}</param>' for k, v in params.items())
    return (
        f'<offer id="{oid}" available="true"><name>{name}</name><price>{price}</price>'
        f"<currencyId>UAH</currencyId><categoryId>1</categoryId>{tags}</offer>"
    )


def test_publish_into_vertical_root_classifies_items(seller):
    ensure_taxonomy(VERTICALS["plumbing"])
    root = Category.objects.get(slug="santekhnika-ta-opalennia")
    source = make_source(
        seller,
        feed(
            offer("1", "Змішувач для кухні Eurosmart хром", "3450", Виробник="Німеччина"),
            offer("2", 'Кран кульовий латунний 1/2" DN15', "265"),
            offer("3", "Радіатор сталевий 22 тип 500x1000", "4200", Тип="22"),
            offer("4", "Щось без категорії", "10"),
        ),
    )
    services.sync_source(source)
    ids = list(SupplierItem.objects.filter(source=source).values_list("pk", flat=True))
    result = services.publish_items(source, ids, category=root)
    assert len(result["created"]) == 4

    by_ext = {i.external_id: i.variant for i in SupplierItem.objects.filter(source=source)}
    assert by_ext["1"].product.category.slug == "zmishuvachi-kukhnia"
    assert by_ext["2"].product.category.slug == "zaporna-armatura"
    assert by_ext["3"].product.category.slug == "radiatory"
    assert by_ext["4"].product.category.slug == "santekhnika-inshe"

    assert by_ext["1"].attributes["Виробник"] == "Німеччина"  # параметр фида
    assert by_ext["1"].attributes["Колір"] == "хром"  # извлечено из названия
    assert by_ext["2"].attributes["Різьба"] == '1/2"' and by_ext["2"].attributes["DN"] == "15"
