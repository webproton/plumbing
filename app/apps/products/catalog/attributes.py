"""Характеристики из названия и описания: різьба, DN, потужність, об'єм, тиск, матеріал, колір, розмір колеса…

Хранятся в ProductVariant.attributes (JSON) — по ним можно строить фильтры витрины без новых колонок в базе.
"""
import re

NUM = r"(\d+(?:[.,]\d+)?)"
# «1/2"», «3/4”», «1 1/4"», «G1/2»
THREAD_RE = re.compile(r"(?:\bg\s?)?(\d\s\d/\d|\d/\d|\d)\s*(?:\"|”|″|''|дюйм)", re.I)
DN_RE = re.compile(r"\b(?:dn|ду)\s*-?\s*(\d{2,3})\b", re.I)
PN_RE = re.compile(r"\bpn\s*-?\s*(\d{1,2})\b", re.I)
POWER_RE = re.compile(NUM + r"\s*(квт|kw|вт|w)\b", re.I)
VOLUME_RE = re.compile(NUM + r"\s*(л|l|літр|литр)(?![a-zа-яіїє])", re.I)
PRESSURE_RE = re.compile(NUM + r"\s*(бар|bar|атм)\b", re.I)
DIAMETER_RE = re.compile(r"(?:ø|⌀|діаметр|диаметр|\bd)\s*" + NUM + r"\s*(?:мм|mm)?", re.I)
SECTIONS_RE = re.compile(r"(\d{1,2})\s*(?:секц|секці|секци)", re.I)
VOLTAGE_RE = re.compile(r"(\d{2})\s*(?:в|v)\b", re.I)
WHEEL_RE = re.compile(r"(\d{2}(?:[.,]5)?)\s*(?:\"|”|″|дюйм)", re.I)
FRAME_RE = re.compile(r"рам[аиы]?\s*(\d{2}(?:[.,]5)?|xs|s|m|l|xl)\b", re.I)

MATERIALS = {
    "латун": "латунь", "нерж": "нержавіюча сталь", "чавун": "чавун", "чугун": "чавун", "мід": "мідь", "медн": "мідь",
    "алюмін": "алюміній", "алюмин": "алюміній", "ppr": "поліпропілен (PPR)", "поліпропілен": "поліпропілен (PPR)",
    "полипропилен": "поліпропілен (PPR)", "металопласт": "металопластик", "металлопласт": "металопластик",
    "сталь": "сталь", "сталев": "сталь", "кераміч": "кераміка", "керамич": "кераміка", "акрил": "акрил",
    "пластик": "пластик",
}
COLORS = {
    "хром": "хром", "чорн": "чорний", "черн": "чорний", "біл": "білий", "бел": "білий", "золот": "золото",
    "бронз": "бронза", "нікел": "нікель", "никел": "нікель", "сатин": "сатин", "графіт": "графіт",
}


def _num(value: str) -> str:
    return value.replace(",", ".")


def extract(text: str, vertical_key: str) -> dict[str, str]:
    low = text.lower()
    found: dict[str, str] = {}

    if vertical_key == "plumbing":
        if m := DN_RE.search(text):
            found["DN"] = m.group(1)
        if m := PN_RE.search(text):
            found["PN"] = m.group(1)
        if m := THREAD_RE.search(text):
            found["Різьба"] = m.group(1) + '"'
        if m := DIAMETER_RE.search(text):
            found["Діаметр, мм"] = _num(m.group(1))
        if m := SECTIONS_RE.search(text):
            found["Кількість секцій"] = m.group(1)
        if m := PRESSURE_RE.search(text):
            found["Тиск"] = f"{_num(m.group(1))} бар"
    if vertical_key in ("plumbing", "tools"):
        if m := POWER_RE.search(text):
            unit = "кВт" if m.group(2).lower() in ("квт", "kw") else "Вт"
            found["Потужність"] = f"{_num(m.group(1))} {unit}"
    if vertical_key == "plumbing" and (m := VOLUME_RE.search(text)):
        found["Об'єм"] = f"{_num(m.group(1))} л"
    if vertical_key == "tools" and (m := VOLTAGE_RE.search(text)) and ("акум" in low or "акку" in low):
        found["Напруга акумулятора"] = f"{m.group(1)} В"
    if vertical_key == "bikes":
        if m := WHEEL_RE.search(text):
            found["Діаметр колеса"] = _num(m.group(1)) + '"'
        if m := FRAME_RE.search(text):
            found["Розмір рами"] = m.group(1).upper()

    if vertical_key != "furniture":
        if material := next((v for k, v in MATERIALS.items() if k in low), None):
            found["Матеріал"] = material
        if color := next((v for k, v in COLORS.items() if re.search(r"(?<!\w)" + k, low)), None):
            found["Колір"] = color
    return found
