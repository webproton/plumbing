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
