"""Дерево направлений в базе и подбор категории/характеристик для импорта (apps.imports.services.publish_items)."""

import re

from ..models import Category
from .attributes import extract
from .taxonomy import VERTICALS, Vertical, classify

# упаковка оптовика («Од. в упак.», «Вага ящ.», «Об'єм ящ.») — покупателю не нужна
PACKAGING_PARAM = re.compile(r"упак|ящ\.|ящик", re.IGNORECASE)


def ensure_taxonomy(vertical: Vertical) -> dict[str, Category]:
    """Создать/обновить дерево направления. → {slug листа: Category} (+ «інше» под ключом vertical.other_slug)."""

    def upsert(slug: str, name: str, parent: Category | None) -> Category:
        category, _ = Category.objects.get_or_create(slug=slug, defaults={"name": name})
        changes = {"name": name, "parent": parent, "vertical": vertical.key}
        if any(getattr(category, attr) != value for attr, value in changes.items()):
            for attr, value in changes.items():
                setattr(category, attr, value)
            category.save()
        return category

    root = upsert(vertical.slug, vertical.name, None)
    leaves = {}
    for section in vertical.sections:
        section_category = upsert(section.slug, section.name, root)
        for leaf in section.leaves:
            leaves[leaf.slug] = upsert(leaf.slug, leaf.name, section_category)
    leaves[vertical.other_slug] = upsert(vertical.other_slug, f"{vertical.name}: інше", root)
    return leaves


class CategoryResolver:
    """
    Если для импорта выбран корень или раздел направления (например «Сантехніка та опалення»),
    каждый товар раскладывается в свою категорию по названию, категории поставщика и параметрам.
    Выбран конкретный лист или ничего — поведение прежнее: все товары в выбранную категорию.
    """

    def __init__(self, base: Category | None):
        self.base = base
        self.vertical = None
        self._leaves: dict[str, Category] | None = None
        if base is not None and base.vertical in VERTICALS and base.children.exists():
            self.vertical = VERTICALS[base.vertical]

    def category_for(self, name: str, supplier_category: str = "", params: dict | None = None) -> Category | None:
        if self.vertical is None:
            return self.base
        if self._leaves is None:
            self._leaves = ensure_taxonomy(self.vertical)
        head = f"{name} {supplier_category}"
        hit = classify(head, self.vertical) or classify(f"{head} {' '.join((params or {}).values())}", self.vertical)
        if hit:
            return self._leaves[hit[1].slug]
        return self._leaves[self.vertical.other_slug] if self.base.parent_id is None else self.base

    def attributes(self, name: str, description: str = "", params: dict | None = None) -> dict:
        """Параметры поставщика + извлечённое из названия (різьба, DN, потужність…); данные поставщика важнее."""
        found = extract(f"{name} {description[:300]}", self.vertical.key) if self.vertical else {}
        own = {k: v for k, v in (params or {}).items() if not PACKAGING_PARAM.search(k)}
        return {**found, **own}
