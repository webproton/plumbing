import pytest

from app.apps.products.catalog.attributes import extract
from app.apps.products.catalog.services import CategoryResolver, ensure_taxonomy
from app.apps.products.catalog.taxonomy import VERTICALS, classify
from app.apps.products.models import Category


def leaf(text, vertical):
    hit = classify(text, VERTICALS[vertical])
    return hit[1].slug if hit else None


def test_slugs_are_unique_across_verticals():
    slugs = []
    for v in VERTICALS.values():
        slugs += [v.slug, v.other_slug] + [s.slug for s in v.sections] + [lf.slug for _, lf in v.leaves]
    assert len(slugs) == len(set(slugs))


@pytest.mark.parametrize(
    "name, expected",
    [
        ("Змішувач для кухні з високим виливом хром", "zmishuvachi-kukhnia"),
        ("Смеситель для ванны с душем", "zmishuvachi-vanna-dush"),
        ("Змішувач Grohe Eurosmart", "zmishuvachi"),
        ("Картридж для змішувача керамічний 35 мм", "komplektuiuchi-zmishuvachiv"),
        ("Картридж PP 5 мкм 10\"", "kartrydzhi"),
        ("Кран кульовий латунний 1/2\" DN15", "zaporna-armatura"),
        ("Радіаторний кран кутовий 1/2\"", "armatura-radiatoriv"),
        ("Фільтр сітчастий 3/4\"", "armatura-radiatoriv"),
        ("Радіатор сталевий 22 тип 500x1000", "radiatory"),
        ("Котел газовий двоконтурний 24 кВт", "kotly-gazovi"),
        ("Бойлер непрямого нагріву 200 л", "boilery-nepriamoho-nahrivu"),
        ("Бойлер електричний 80 л", "boilery"),
        ("Насос циркуляційний для котла 25-60", "nasosy"),
        ("Труба PPR 20 мм PN20", "truby"),
        ("Кутник PPR 20х90°", "fitynhy"),
        ("Фільтр-глечик 3,5 л", "filtry-hlechyky"),
        ("Система зворотного осмосу 5 ступенів", "osmos"),
        ("Унітаз підвісний з інсталяцією", "unitazy-instaliatsii"),
    ],
)
def test_plumbing_classification(name, expected):
    assert leaf(name, "plumbing") == expected


@pytest.mark.parametrize(
    "name, vertical, expected",
    [
        ("Ключ розвідний 250 мм", "tools", "kliuchi"),
        ("Шуруповерт акумуляторний 18 В", "tools", "dryli-shurupoverty"),
        ("Диск відрізний для болгарки 125 мм", "tools", "dysky-sverdla"),
        ("Набір викруток 6 шт", "tools", "vykrutky-bity"),
        ("Велосипедний шолом з вентиляцією", "bikes", "velo-sholomy"),
        ("Покришка 28\" антипрокол", "bikes", "velo-pokryshky"),
        ("Міський велосипед 28\" рама M", "bikes", "velosypedy-dorosli"),
        ("Дитячий велосипед 16\"", "bikes", "dytiachi-velosypedy"),
        ("Угловой диван Мейсон", "furniture", "divany"),
    ],
)
def test_other_verticals(name, vertical, expected):
    assert leaf(name, vertical) == expected


def test_attributes_from_name():
    attrs = extract('Кран кульовий латунний 1/2" DN15 PN40 хром', "plumbing")
    assert attrs == {"DN": "15", "PN": "40", "Різьба": '1/2"', "Матеріал": "латунь", "Колір": "хром"}
    assert extract("Котел газовий 24 кВт", "plumbing")["Потужність"] == "24 кВт"
    assert extract("Бойлер 80 л", "plumbing")["Об'єм"] == "80 л"
    assert extract("Радіатор алюмінієвий 10 секцій", "plumbing")["Кількість секцій"] == "10"
    assert extract('Велосипед 27,5" рама L', "bikes") == {"Діаметр колеса": '27.5"', "Розмір рами": "L"}


@pytest.mark.django_db
def test_ensure_taxonomy_builds_tree_and_reuses_existing_categories():
    old = Category.objects.create(name="Диваны", slug="divany")
    leaves = ensure_taxonomy(VERTICALS["furniture"])
    old.refresh_from_db()
    assert leaves["divany"].pk == old.pk and old.vertical == "furniture"
    assert old.parent.parent.slug == "mebli" and old.parent.parent.parent is None

    count = Category.objects.count()
    ensure_taxonomy(VERTICALS["furniture"])
    assert Category.objects.count() == count  # повторно не дублирует

    plumbing = ensure_taxonomy(VERTICALS["plumbing"])
    mixer = plumbing["zmishuvachi-kukhnia"]
    assert mixer.vertical == "plumbing" and mixer.parent.slug == "santekhnika"


@pytest.mark.django_db
def test_resolver_only_classifies_for_vertical_nodes():
    leaves = ensure_taxonomy(VERTICALS["plumbing"])
    root = Category.objects.get(slug="santekhnika-ta-opalennia")
    resolver = CategoryResolver(root)
    assert resolver.category_for("Змішувач для кухні") == leaves["zmishuvachi-kukhnia"]
    assert resolver.category_for("Щось незрозуміле") == leaves["santekhnika-inshe"]
    assert resolver.attributes("Кран 1/2\"", params={"Матеріал": "сталь"})["Матеріал"] == "сталь"

    fixed = leaves["radiatory"]
    assert CategoryResolver(fixed).category_for("Змішувач для кухні") == fixed  # лист — всё как раньше
    assert CategoryResolver(None).category_for("Змішувач") is None
