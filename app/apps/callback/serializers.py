from django.utils.translation import gettext as _
from rest_framework import serializers

from app.apps.orders.validators import validate_phone_number

from .models import SiteSettings


class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ("phone", "email", "telegram", "whatsapp")
        read_only_fields = fields


class CallbackSerializer(serializers.Serializer):
    # украинский номер: +380XXXXXXXXX / 0XXXXXXXXX → нормализуется к +380XXXXXXXXX
    phone = serializers.CharField(max_length=20, validators=[], trim_whitespace=True)
    email = serializers.EmailField(required=False, allow_blank=True, trim_whitespace=True)
    telegram = serializers.CharField(required=False, allow_blank=True, max_length=50, trim_whitespace=True)

    def validate_phone(self, value):
        return validate_phone_number(value)


class ShopSettingsSerializer(serializers.ModelSerializer):
    """Настройки магазина для кабинета администратора: контакты, реквизиты для счёта, отправитель НП."""

    class Meta:
        model = SiteSettings
        fields = [
            "phone", "email", "telegram", "whatsapp",
            "legal_name", "tax_id", "iban", "bank_name", "legal_address", "vat_payer", "invoice_note",
            "np_sender_city_ref", "np_sender_city_name", "np_sender_warehouse_ref", "np_sender_warehouse_name",
            "np_sender_phone",
        ]  # fmt: skip
        extra_kwargs = {"phone": {"required": False}}

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

    def validate_np_sender_phone(self, value):
        return validate_phone_number(value) if value else value
