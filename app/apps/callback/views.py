import os
import requests
import html
import random
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework import serializers, status
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import SiteSettings
from .serializers import SiteSettingsSerializer,CallbackSerializer
from django_ratelimit.decorators import ratelimit


TELEGRAM_BOT_TOKEN = os.getenv("TOKEN_BOT")
TELEGRAM_MANAGERS = os.getenv("MANAGERS", "").split(",")

current_manager_index = 0

def send_telegram_message(chat_id, text):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    resp = requests.post(url, data=payload)
    if not resp.ok:
        print("Ошибка отправки:", resp.text)
    return resp

# --- Основной эндпоинт ---
@api_view(["POST"])
@permission_classes([AllowAny])
@ratelimit(key="ip", rate="10/m", block=True)
def callback_request(request):
    serializer = CallbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    if not TELEGRAM_MANAGERS or not TELEGRAM_BOT_TOKEN:
        return Response(
            {"error": "Telegram config missing"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    manager_chat_id = random.choice(TELEGRAM_MANAGERS)

    phone = html.escape(data["phone"])
    email = html.escape(data.get("email", "")) or "—"
    telegram = html.escape(data.get("telegram", "")) or "—"

    text = (
        f"📞 <b>Новая заявка на звонок</b>\n\n"
        f"Телефон: {phone}\n"
        f"Email: {email}\n"
        f"Telegram: {telegram}"
    )

    resp = send_telegram_message(manager_chat_id, text)
    if not resp.ok:
        return Response({"error": "Failed to send message"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    return Response({"status": "ok", "manager": manager_chat_id}, status=status.HTTP_201_CREATED)



class SiteSettingsView(APIView):
    permission_classes = [AllowAny] 
    def get(self, request):
        settings = SiteSettings.objects.first()
        if not settings:
            return Response({"error": "settings not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = SiteSettingsSerializer(settings)
        return Response(serializer.data)

