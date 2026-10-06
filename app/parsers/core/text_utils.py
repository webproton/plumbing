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

    return " ".join(
        str(x).strip()
        for x in row
        if x not in (None, "")
    )


def normalize_text(s):
    """
    Убирает лишние пробелы / табы / переносы
    """

    if s is None:
        return ""

    return re.sub(r"\s+", " ", str(s)).strip()


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

    return normalize_text(
        "\n".join(
            row_text(r)
            for r in rows
            if r
        )
    )