# parsers/core/date_utils.py
import re
from datetime import datetime


# =========================
# DATE PATTERNS
# =========================

DATE_PATTERNS = [
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}\.\d{1,2}\.\d{4}\b",
    r"\b\d{1,2}/\d{1,2}/\d{4}\b",
    r"\b\d{1,2}\s+(?:января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)\s+\d{4}\b",
    r"\b\d{1,2}\s+(?:січня|лютого|березня|квітня|травня|червня|липня|серпня|вересня|жовтня|листопада|грудня)\s+\d{4}\b",
]


MONTH_MAP = {
    "янв": 1, "січ": 1, "фев": 2, "лют": 2, "мар": 3, "бер": 3,
    "апр": 4, "кві": 4, "мая": 5, "тра": 5, "июн": 6, "чер": 6,
    "июл": 7, "лип": 7, "авг": 8, "сер": 8, "сен": 9, "вер": 9,
    "окт": 10, "жов": 10, "ноя": 11, "лис": 11, "дек": 12, "гру": 12
}

# =========================
# EXTRACT DATE
# =========================

def extract_date(text: str):
    """
    Универсальный extractor даты
    """

    if not text:
        return None

    for pattern in DATE_PATTERNS:
        match = re.search(pattern, text, re.I)

        if match:
            return normalize_date(match.group(0))

    return None


# =========================
# NORMALIZE DATE
# =========================

def normalize_date(date_str: str):
    if not date_str:
        return None
    date_str = re.sub(r'\s+', ' ', date_str.strip().lower())

    # Попытка распарсить стандартные числовые форматы (DMY в приоритете)
    formats = ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%m/%d/%Y"]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).date().isoformat()
        except ValueError:
            pass

    # Парсинг текстовых месяцев (RU/UA)
    try:
        parts = date_str.split()
        if len(parts) >= 3:
            day = int(parts[0])
            year = int(parts[2])
            month_text = parts[1][:3]
            month = MONTH_MAP.get(month_text)
            if month:
                return datetime(year, month, day).date().isoformat()
    except ValueError:
        pass

    return date_str