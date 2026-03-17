from rest_framework import viewsets, status, permissions,filters
from rest_framework.views import APIView
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.response import Response
from .models import TelemetryEvent
from .serializers import TelemetryEventSerializer
from app.apps.telemetry.services import antifraud, scoring
from app.apps.telemetry.utils import fingerprints
from django.conf import settings
from device_detector import DeviceDetector
# Правильный импорт
import os
from django.contrib.gis.geoip2 import GeoIP2


import logging
logger = logging.getLogger("antifraud")


def log_event(reason: str, ip: str, data: dict, extra: dict = None):
    """Лог антифрод-событий"""
    logger.warning(
        f"[ANTIFRAUD] Blocked: {reason} | ip={ip} | device_id={data.get('device_id')} | extra={extra}"
    )


def parse_ua(user_agent):
    dd = DeviceDetector(user_agent)
    dd.parse()

    device_type = dd.device_type()      # smartphone, tablet, desktop, bot
    brand = dd.device_brand()           # Apple, Samsung
    model = dd.device_model()           # iPhone 14, Galaxy S23

    os_name = dd.os_name()              # Android, iOS, Windows
    os_version = dd.os_version()

    browser_name = dd.client_name()     # Chrome, Safari
    browser_version = dd.client_version()


    return {
        "device_type": device_type,
        "device_vendor": brand,
        "device_model": model,
        "os_name": os_name,
        "os_version": os_version,
        "browser_name": browser_name,
        "browser_version": browser_version,
    }
# --------------------------
# 1️⃣ CRUD для админки/аналитики
# --------------------------
class TelemetryEventViewSet(viewsets.ModelViewSet):
    queryset = TelemetryEvent.objects.all()
    serializer_class = TelemetryEventSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter, filters.SearchFilter]
    filterset_fields = ['event_type', 'browser', 'os', 'country', 'device_type']
    search_fields = ['page_url', 'referrer', 'event_data']
    ordering_fields = ['created_at', 'duration_ms']
    # Можно добавить фильтры, поиск , пагинацию

# --------------------------
# Сбор данных с фронта + антифрод
# --------------------------
class TelemetryCollectAPIView(APIView):
    """Точка сбора телеметрии с фронта с антифрод-проверками"""
    permission_classes = [permissions.AllowAny]


    def get_client_ip_chain(self, request):
        """Возвращает цепочку IP (клиент + прокси)"""
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        if x_forwarded_for:
            ip_list = [ip.strip() for ip in x_forwarded_for.split(",")]
            return ip_list
        return [request.META.get("REMOTE_ADDR")]

    def post(self, request):
        data = request.data.copy()

        # --------------------------
        # Сеть / клиент
        # --------------------------
        ip_chain = self.get_client_ip_chain(request)
        ip_address = ip_chain[0]

        data["ip_address"] = ip_address           # реальный IP
        data["ip_chain"] = ",".join(ip_chain)      # вся цепочка
        # ✅ Если это dev IP — пропускаем антифрод полностью
  
        # Если это dev IP или DEBUG режим — пропускаем антифрод
        if antifraud.is_dev_environment(ip_address) or settings.DEBUG:
            serializer = TelemetryEventSerializer(data=data, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response({"status": "ok"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
                
        # --------------------------
        # Гео-данные (город, страна)
        # --------------------------
        try:
            g = GeoIP2()
            geo = g.city(ip_address)   # словарь с инфой
            data["city"] = geo.get("city")
            data["country"] = geo.get("country_name")
            data["latitude"] = geo.get("latitude")
            data["longitude"] = geo.get("longitude")
        except Exception as e:
            # если не удалось определить (например localhost или база не подключена)
            data["city"] = None
            data["country"] = None
        user_agent = request.META.get("HTTP_USER_AGENT", "")
        device_info = parse_ua(user_agent)

        # Добавляем в data для сериализации
        data["device_type"] = device_info.get("device_type")
        data["device_model"] = device_info.get("device_model")
        data["device_vendor"] = device_info.get("device_vendor")
        data["os"] = device_info.get("os_name")
        data["os_version"] = device_info.get("os_version")
        data["browser"] = device_info.get("browser_name")
        data["browser_version"] = device_info.get("browser_version")
        # print(data,'<<<<<<<<<<<<data')

        # Fingerprint
        signature = fingerprints.fingerprint_signature(data)
        data["fingerprint_signature"] = signature
        # ✅ В dev просто сохраняем телеметрию без антифрода
        if settings.DEBUG:
            serializer = TelemetryEventSerializer(data=data, context={"request": request})
            if serializer.is_valid():
                serializer.save()
                return Response({"status": "ok"}, status=status.HTTP_201_CREATED)
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # --------------------------
        # Fingerprint         # Антифрод-проверки (только в PROD)
        # --------------------------


        if fingerprints.is_suspicious_fingerprint(data):
            antifraud.log_event("fingerprint_suspicious", ip_chain[0], data)
            return Response(
                {"status": "blocked", "reason": "fingerprint suspicious"},
                status=status.HTTP_403_FORBIDDEN
            )

        # --------------------------
        # Скоринг
        # --------------------------
        risk = scoring.risk_score(data)
        if risk >= 60:
            antifraud.log_event("high_risk", ip_chain[0], data, extra={"risk": risk})
            return Response(
                {"status": "blocked", "reason": f"high_risk ({risk})"},
                status=status.HTTP_403_FORBIDDEN
            )

        # --------------------------
        # Антифрод проверки
        # --------------------------
        device_id = data.get("device_id")
        session_id = data.get("session_id")
        timezone = data.get("timezone")

        if antifraud.is_too_frequent(device_id):
            antifraud.log_event("too_frequent", ip_chain[0], data)
            return Response({"status": "blocked", "reason": "too_frequent"}, status=403)

        if antifraud.has_bad_user_agent(user_agent):
            antifraud.log_event("bad_user_agent", ip_chain[0], data,  extra={"ua": user_agent, "browser": data["browser"], "device_model": data["device_model"]})
            return Response({"status": "blocked", "reason": "bad_user_agent"}, status=403)

        if antifraud.ip_timezone_mismatch(ip_chain[0], timezone):
            antifraud.log_event("ip_timezone_mismatch", ip_chain[0], data)
            return Response({"status": "blocked", "reason": "ip_timezone_mismatch"}, status=403)

        if antifraud.too_many_fingerprints_for_ip(ip_chain[0]):
            antifraud.log_event("fingerprint_spam", ip_chain[0], data)
            return Response({"status": "blocked", "reason": "fingerprint_spam"}, status=403)

        if antifraud.is_too_fast(session_id):
            antifraud.log_event("too_fast", ip_chain[0], data)
            return Response({"status": "blocked", "reason": "too_fast"}, status=403)
        
        

        # --------------------------
        # Сохраняем если всё ок
        # --------------------------
        serializer = TelemetryEventSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            return Response({"status": "ok"}, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)