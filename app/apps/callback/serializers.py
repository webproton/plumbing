from django.utils.translation import gettext as _
from rest_framework import serializers

from app.apps.orders.validators import validate_phone_number

from .models import SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        # ID пикселей и код Google — публичные (видны в коде любой страницы), нужны витрине
        fields = (
            "phone", "email", "telegram", "whatsapp", "ga4_id", "gtm_id", "meta_pixel_id", "tiktok_pixel_id",
            "google_site_verification", "pickup_address", "opening_hours", "google_business_url",
        )  # fmt: skip
        read_only_fields = fields


class CallbackSerializer(serializers.Serializer):
    # украинский номер: +380XXXXXXXXX / 0XXXXXXXXX → нормализуется к +380XXXXXXXXX
    phone = serializers.CharField(max_length=20, validators=[], trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True, trim_whitespace=True)
    telegram = serializers.CharField(required=False, allow_blank=True, max_length=50, trim_whitespace=True)

    def validate_phone(self, value):
        return validate_phone_number(value)


def _id_validator(field):
    """ID пикселей и канал — строгий формат (вставляются в скрипт на странице)."""

    def validate(self, value):
        from app.apps.marketing.validators import clean_id

        cleaned = clean_id(field, value)
        if cleaned is None:
            raise serializers.ValidationError(_("Неверный формат"))
        return cleaned

    return validate


STRICT_FORMAT_FIELDS = (
    "ga4_id",
    "gtm_id",
    "meta_pixel_id",
    "tiktok_pixel_id",
    "telegram_channel",
    "google_site_verification",
)


class ShopSettingsSerializer(serializers.ModelSerializer):
    """Настройки магазина для кабинета администратора: контакты, реквизиты для счёта, отправитель НП."""

    class Meta:
        model = SiteSettings
        fields = [
            "phone", "email", "telegram", "whatsapp",
            "legal_name", "tax_id", "iban", "bank_name", "legal_address", "vat_payer", "invoice_note",
            "np_sender_city_ref", "np_sender_city_name", "np_sender_warehouse_ref", "np_sender_warehouse_name",
            "np_sender_phone",
            "ga4_id", "gtm_id", "meta_pixel_id", "tiktok_pixel_id", "feeds_enabled", "telegram_channel",
            "telegram_autopost", "notify_customers",
            "google_site_verification", "pickup_address", "opening_hours", "google_business_url",
        ]  # fmt: skip
        # длину проверяет строгий формат ID — так видны все ошибки сразу
        extra_kwargs = {
            "phone": {"required": False},
            **{f: {"max_length": None} for f in STRICT_FORMAT_FIELDS},
        }

    def validate_iban(self, value):
        value = value.replace(" ", "").upper()
        if value and not (value.startswith("UA") and len(value) == 29 and value[2:].isdigit()):
            raise serializers.ValidationError(_("IBAN: UA и 27 цифр"))
        return value

    def validate_tax_id(self, value):
        value = value.strip()
        if value and not (value.isdigit() and len(value) in (8, 10)):
            raise serializers.ValidationError(_("ЄДРПОУ — 8 цифр, ІПН — 10 цифр"))
        return value

    validate_ga4_id = _id_validator("ga4_id")
    validate_gtm_id = _id_validator("gtm_id")
    validate_meta_pixel_id = _id_validator("meta_pixel_id")
    validate_tiktok_pixel_id = _id_validator("tiktok_pixel_id")
    validate_telegram_channel = _id_validator("telegram_channel")
    validate_google_site_verification = _id_validator("google_site_verification")

    def validate_np_sender_phone(self, value):
        return validate_phone_number(value) if value else value
