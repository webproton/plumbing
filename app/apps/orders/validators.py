import re

from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError

NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '’\-][^\W\d_]+)*$")


def validate_phone_number(value):
    """Телефон Украины: +380XXXXXXXXX или 0XXXXXXXXX → нормализуется к +380XXXXXXXXX."""
    digits = re.sub(r"\D", "", value or "")
    if digits.startswith("0") and len(digits) == 10:
        return "+380" + digits[1:]
    if digits.startswith("380") and len(digits) == 12:
        return "+" + digits
    raise ValidationError(_("Номер телефона должен быть в формате +380XXXXXXXXX"))


def validate_person_name(value):
    """Буквы любого алфавита, пробелы, дефис и апостроф (Мар'яна, Анна-Марія)."""
    value = " ".join((value or "").split())
    if not value or not NAME_RE.match(value):
        raise ValidationError(_("Имя может содержать только буквы, пробел, дефис и апостроф."))
    return value
