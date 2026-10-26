from django.utils.text import slugify
from transliterate import translit

# Украинские буквы, которых нет в русском наборе transliterate
_UA = str.maketrans(
    {"і": "i", "І": "I", "ї": "yi", "Ї": "Yi", "є": "ye", "Є": "Ye", "ґ": "g", "Ґ": "G", "'": "", "’": ""}
)


MAX_SLUG = 200  # поле — 255; запас на «-2», «-3»… Длинные названия поставщиков после транслитерации длиннее 255


def make_slug(text: str, fallback: str = "item") -> str:
    """Латинский slug из кириллицы (рус./укр.): «Смесители» → «smesiteli». Django slugify кириллицу выбрасывает."""
    latin = translit((text or "").translate(_UA), "ru", reversed=True)
    slug = slugify(latin)
    if len(slug) > MAX_SLUG:
        slug = slug[:MAX_SLUG].rsplit("-", 1)[0]
    return slug or fallback


def unique_slug(model, text: str, fallback: str = "item", exclude_pk=None) -> str:
    base = make_slug(text, fallback)
    slug, counter = base, 1
    qs = model.objects.exclude(pk=exclude_pk) if exclude_pk else model.objects
    while qs.filter(slug=slug).exists():
        counter += 1
        slug = f"{base}-{counter}"
    return slug
