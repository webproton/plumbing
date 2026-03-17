from django.utils.deprecation import MiddlewareMixin
from django.http import JsonResponse
from app.apps.telemetry.services import antifraud, scoring
from app.apps.telemetry.utils import fingerprints

SAFE_PATHS = [
    "/api/telemetry/collect/",  # телеметрия всегда разрешена
    "/api/products/",
    "/api/category/",
    "/api/wishlist/",
    "/api/new_products/",
    "/account/",
    "/api/accounts/",
    "/api/orders/",
]


class AntiFraudMiddleware(MiddlewareMixin):
    def process_request(self, request):
        path = request.path

        # Разрешаем безопасные ручки
        if any(path.startswith(p) for p in SAFE_PATHS):
            return None

        ip = self.get_client_ip(request)

        # Пропускаем SAFE_PATHS и dev IP
        if any(path.startswith(p) for p in SAFE_PATHS) or antifraud.is_dev_environment(ip):
            return None


        ua = request.META.get("HTTP_USER_AGENT", "")

        data = {
            "ip_address": ip,
            "device_id": request.META.get("HTTP_X_DEVICE_ID"),
            "session_id": request.META.get("HTTP_X_SESSION_ID"),
            "user_agent": ua,
        }
        data["fingerprint_signature"] = fingerprints.fingerprint_signature(data)

        # Получаем ASN
        data["asn"] = antifraud.get_asn(ip)  # <-- сюда добавляем
        if data["asn"] == "Unknown":
            antifraud.log_event("unknown_asn", ip, data)
        
        # Можно добавить проверку на подозрительные провайдеры:
        if data["asn"] in ["SomeBadISP", "AnotherSuspiciousOrg"]:
            antifraud.log_event("bad_asn", ip, data)
            return JsonResponse({"status": "blocked", "reason": "bad_asn"}, status=403)

        # Проверки
        if antifraud.has_bad_user_agent(ua, ip):
            antifraud.log_event("bad_user_agent", ip, data)
            return JsonResponse({"status": "blocked", "reason": "bad_user_agent"}, status=403)

        if antifraud.is_too_frequent(data.get("device_id"), ip):
            antifraud.log_event("too_frequent", ip, data)
            return JsonResponse({"status": "blocked", "reason": "too_frequent"}, status=403)

        if antifraud.is_too_fast(data.get("session_id"), ip):
            antifraud.log_event("too_fast", ip, data)
            return JsonResponse({"status": "blocked", "reason": "too_fast"}, status=403)

        if antifraud.too_many_fingerprints_for_ip(ip):
            antifraud.log_event("too_many_fingerprints", ip, data)
            return JsonResponse({"status": "blocked", "reason": "too_many_fingerprints"}, status=403)

        if antifraud.ip_timezone_mismatch(ip, request.META.get("HTTP_X_TIMEZONE")):
            antifraud.log_event("ip_timezone_mismatch", ip, data)
            return JsonResponse({"status": "blocked", "reason": "ip_timezone_mismatch"}, status=403)

        # Скоринг
        risk = scoring.risk_score(data)
        if risk >= 60:
            antifraud.log_event("high_risk", ip, data, extra={"risk": risk})
            return JsonResponse(
                {"status": "blocked", "reason": f"high_risk ({risk})"},
                status=403,
            )

        return None

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
        remote_addr = request.META.get("REMOTE_ADDR")

        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = remote_addr


        return client_ip
