from rest_framework import serializers
from .models import SiteSettings

class SiteSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = SiteSettings
        fields = ("phone", "email", "telegram", "whatsapp")
        read_only_fields = fields


class CallbackSerializer(serializers.Serializer):
    phone = serializers.RegexField(
        regex=r'^\+?\d{7,15}$',
        max_length=20,
        error_messages={"invalid": "Введите корректный номер телефона."}
    )
    email = serializers.EmailField(required=False, allow_blank=True, trim_whitespace=True)
    telegram = serializers.CharField(required=False, allow_blank=True, max_length=50, trim_whitespace=True)
