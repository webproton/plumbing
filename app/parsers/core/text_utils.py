# parsers/core/text_utils.py

import re

# =========================
# TEXT / ROW HELPERS
# =========================


def row_text(row):
    """
    Склеивает строку Excel в единый текст
    """

    # защита от None
    if not row:
        return ""

    return " ".join(str(x).strip() for x in row if x not in (None, ""))


def normalize_text(s):
    """
    Убирает лишние пробелы / табы / переносы
    """

    if s is None:
        return ""

    return re.sub(r"\s+", " ", str(s)).strip()


# Латинские буквы, которые в выгрузках 1С и старых шаблонах стоят вместо кириллических
# («Кiлькiсть», «Цiна» с латинской i) — визуально одинаковы, но ключевые слова не находятся.
_LOOKALIKES = str.maketrans("iaeocpxykmthb", "іаеосрхукмтнв")
_CYRILLIC = re.compile(r"[а-яіїєґё]", re.IGNORECASE)


def fold_lookalikes(text):
    """
    Нормализация текста заголовков колонок: нижний регистр, пробелы, латинские двойники кириллицы
    заменяются в словах, где уже есть кириллица («кiлькiсть» → «кількість»). Английские слова не трогаются.
    """
    words = normalize_text(text).lower().split(" ")
    return " ".join(w.translate(_LOOKALIKES) if _CYRILLIC.search(w) else w for w in words)


# Обратное направление — для артикулов: коды латинские, а в них печатают кириллические «С», «Т», «Н»…
_CODE_LOOKALIKES = str.maketrans("АВЕКМНОРСТХУІЅЈ", "ABEKMHOPCTXYISJ")


def code_key(value) -> str:
    """Ключ сравнения артикула/штрихкода: верхний регистр, без пробелов, кириллические двойники → латиница."""
    return re.sub(r"\s+", "", normalize_text(value).upper()).translate(_CODE_LOOKALIKES)


def clean(v):
    """
    Базовая очистка значения
    """

    if v in (None, ""):
        return None

    value = str(v).strip()

    return value or None


# =========================
# COMMON TEXT BUILDER
# =========================


def build_text(rows):

    if not rows:
        return ""

    return normalize_text("\n".join(row_text(r) for r in rows if r))
