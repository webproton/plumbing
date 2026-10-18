from django.utils.translation import gettext as _
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from app.core import telegram

from .models import SiteSettings
from .serializers import CallbackSerializer, SiteSettingsSerializer


@api_view(["POST"])
@permission_classes([AllowAny])
@ratelimit(key="ip", rate="10/m", block=True)
def callback_request(request):
    """Заявка «перезвоните мне» → сообщение менеджеру в Telegram."""
    serializer = CallbackSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data

    chat_id = telegram.next_manager_chat_id()
    if not chat_id:
        return Response({"detail": _("Сервис временно недоступен")}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

    e = telegram.esc
    text = (
        "📞 <b>Новая заявка на звонок</b>\n\n"
        f"Телефон: {e(data['phone'])}\n"
        f"Email: {e(data.get('email'))}\n"
        f"Telegram: {e(data.get('telegram'))}"
    )
    if not telegram.send_message(chat_id, text):
        return Response(
            {"detail": _("Не удалось отправить заявку, попробуйте позже")}, status=status.HTTP_503_SERVICE_UNAVAILABLE
        )
    return Response({"status": "ok"}, status=status.HTTP_201_CREATED)


class SiteSettingsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        settings_obj = SiteSettings.objects.first()
        if not settings_obj:
            return Response({"detail": "settings not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response(SiteSettingsSerializer(settings_obj).data)
