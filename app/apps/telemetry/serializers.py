# app/serializers.py
from rest_framework import serializers
from .models import TelemetryEvent

class TelemetryEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryEvent
        exclude = ("user",)  # user не принимаем с фронта

    def create(self, validated_data):
        request = self.context.get("request")
        if request and request.user.is_authenticated:
            validated_data["user"] = request.user
        else:
            validated_data["user"] = None  # или raise serializers.ValidationError("User must be authenticated")
        return super().create(validated_data)
webproton norm no ne polnuy 