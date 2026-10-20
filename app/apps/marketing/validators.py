"""ID пикселей вставляются в <script> на странице — принимаем только строгий формат."""

import re

PATTERNS = {
    "ga4_id": re.compile(r"^G-[A-Z0-9]{4,15}$"),
    "gtm_id": re.compile(r"^GTM-[A-Z0-9]{4,12}$"),
    "meta_pixel_id": re.compile(r"^\d{5,20}$"),
    "tiktok_pixel_id": re.compile(r"^[A-Z0-9]{10,30}$"),
    "telegram_channel": re.compile(r"^(@[A-Za-z0-9_]{5,32}|-100\d{6,16})$"),
}


def clean_id(field: str, value: str) -> str:
    value = (value or "").strip()
    if field != "telegram_channel":
        value = value.upper()
    return value if not value or PATTERNS[field].match(value) else None
