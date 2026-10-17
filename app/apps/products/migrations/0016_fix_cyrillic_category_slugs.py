"""
Category.save() вызывал slugify без транслитерации: у кириллических категорий slug получался
пустым ("") или вида "-1", и фильтр каталога ?category=<slug> по ним не работал.
Перегенерируем такие slug транслитом («Смесители» → «smesiteli»).
"""
import re

from django.db import migrations

from app.apps.products.utils.slugs import make_slug


def forwards(apps, schema_editor):
    Category = apps.get_model("products", "Category")
    taken = set(Category.objects.exclude(slug__isnull=True).values_list("slug", flat=True))
    fixed = 0
    for cat in Category.objects.order_by("id"):
        if cat.slug and not re.fullmatch(r"-?\d*|-\d+", cat.slug):
            continue
        base = make_slug(cat.name, fallback=f"category-{cat.pk}")
        slug, n = base, 1
        while slug in taken:
            n += 1
            slug = f"{base}-{n}"
        taken.discard(cat.slug)
        taken.add(slug)
        Category.objects.filter(pk=cat.pk).update(slug=slug)
        fixed += 1
    if fixed:
        print(f"\n  [products.0016] исправлено slug категорий: {fixed}")


class Migration(migrations.Migration):
    dependencies = [("products", "0015_stock_decimal")]

    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
