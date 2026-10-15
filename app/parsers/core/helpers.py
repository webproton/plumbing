# parsers/core/helpers.py
import re

from .text_utils import normalize_text, row_text

# not using

# =========================
# BLOCK HELPERS
# =========================


def extract_block(rows, start_labels, stop_labels=None, max_rows=5):
    """
    Забирает блок строк после label

    Используется когда:
    - адреса
    - покупатель
    - поставщик
    """

    result = []
    started = False

    for _i, row in enumerate(rows):
        text = row_text(row)
        text_l = text.lower()

        if not started and any(label in text_l for label in start_labels):
            started = True
            continue

        if started:
            if stop_labels and any(label in text_l for label in stop_labels):
                break

            result.append(text)

            if len(result) >= max_rows:
                break

    return normalize_text(" ".join(result)) if result else None


def extract_after_label(row, labels):
    """Извлекает текст после метки (Поставщик:, Покупатель: и т.д.)"""
    row = ["" if x is None else str(x).strip() for x in row]
    found = False
    result = []
    for cell in row:
        if not cell:
            continue
        cell_l = cell.lower()
        if not found and any(label in cell_l for label in labels):
            found = True
            continue
        if found:
            if any(x in cell_l for x in ["поставщик", "покупатель", "артикул", "итого", "всего"]):
                break
            result.append(cell)
    return normalize_text(", ".join(result)) if result else None


def clean_entity(text: str):
    if not text:
        return None

    t = text.strip()

    # мусорные строки
    if re.search(r"(тел\.?|уважаемые|клиенты|р\/рах|адреса)", t, re.I):
        return None

    # слишком короткое / длинное
    if len(t) < 3 or len(t) > 80:
        return None

    # если есть длинные числа (счета / артикулы / телефоны)
    # слишком много цифр подряд → скорее мусор
    if len(re.findall(r"\d", t)) > 12:
        return None
    return t
