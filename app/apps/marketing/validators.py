"""ID пикселей и код подтверждения Google вставляются в страницу — принимаем только строгий формат."""

import re

CASE_SENSITIVE = {"telegram_channel", "google_site_verification"}
PATTERNS = {
    "ga4_id": re.compile(r"^G-[A-Z0-9]{4,15}$"),
    "gtm_id": re.compile(r"^GTM-[A-Z0-9]{4,12}$"),
    "meta_pixel_id": re.compile(r"^\d{5,20}$"),
    "tiktok_pixel_id": re.compile(r"^[A-Z0-9]{10,30}$"),
    "telegram_channel": re.compile(r"^(@[A-Za-z0-9_]{5,32}|-100\d{6,16})$"),
    "google_site_verification": re.compile(r"^[A-Za-z0-9_-]{20,100}$"),
}


def clean_id(field: str, value: str) -> str:
    value = (value or "").strip()
    if field == "google_site_verification":
        # обычно вставляют весь тег <meta name="google-site-verification" content="…" /> — берём код
        found = re.search(r"""content=["']([^"']+)["']""", value)
        value = found.group(1).strip() if found else value
    if field not in CASE_SENSITIVE:
        value = value.upper()
    return value if not value or PATTERNS[field].match(value) else None
