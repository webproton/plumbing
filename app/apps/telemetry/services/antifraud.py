# apps/telemetry/services/antifraud.py
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import geoip2.database

from ..models import TelemetryEvent
import ipaddress
import logging
logger = logging.getLogger("antifraud")

CITY_DB = "./app/geoip/GeoLite2-City.mmdb"
COUNTRY_DB = "./app/geoip/GeoLite2-Country.mmdb"
ASN_DB = "./app/geoip/GeoLite2-ASN.mmdb"


reader_city = geoip2.database.Reader(CITY_DB)
reader_asn = geoip2.database.Reader(ASN_DB)
reader_country = geoip2.database.Reader(COUNTRY_DB)

# Минимальный список "плохих" юзерагентов
BAD_AGENTS = ["curl", "python", "bot", "scrapy", "wget", "httpclient"]
DEV_IP_WHITELIST = getattr(settings, "DEV_IP_WHITELIST", ["127.0.0.1", "10.0.0.0/8","192.168.0.0/16"])

def is_dev_environment(ip: str) -> bool:
    if settings.DEBUG:
        return True
    if not ip:
        return False
    try:
        client_ip = ipaddress.ip_address(ip)
        for dev_ip in DEV_IP_WHITELIST:
            if "/" in dev_ip:
                if client_ip in ipaddress.ip_network(dev_ip):
                    return True
            elif str(client_ip) == dev_ip:
                return True
    except ValueError:
        return False
    return False


def has_bad_user_agent(user_agent: str, ip: str) -> bool:
    if is_dev_environment(ip):
        return False
    if not user_agent:
        return True
    ua_lower = user_agent.lower()
    return any(bad in ua_lower for bad in BAD_AGENTS)


def is_too_frequent(device_id: str, ip: str, threshold: int = 20, seconds: int = 60) -> bool:
    if is_dev_environment(ip):
        return False
    if not device_id:
        return False
    now = timezone.now()
    recent_events = TelemetryEvent.objects.filter(
        device_id=device_id,
        created_at__gte=now - timedelta(seconds=seconds)
    ).count()
    return recent_events > threshold

def is_too_fast(session_id: str, ip: str, min_seconds: int = 3) -> bool:
    """Слишком быстрое повторное событие (например, клик-боты)"""
    if is_dev_environment(ip):
        return False
    if not session_id:
        return False
    events = TelemetryEvent.objects.filter(session_id=session_id).order_by("created_at")
    if events.count() >= 2:
        diff = (events.last().created_at - events.first().created_at).total_seconds()
        return diff < min_seconds
    return False


def too_many_fingerprints_for_ip(ip_address: str, limit: int = 10) -> bool:
    """Слишком много уникальных fingerprint'ов с одного IP (подозрительная активность)"""
    if is_dev_environment(ip_address):
        return False
    if not ip_address:
        return False
    count = (
        TelemetryEvent.objects.filter(ip_address=ip_address)
        .values("canvas_hash", "webgl_vendor", "audio_hash")
        .distinct()
        .count()
    )
    return count > limit

def ip_timezone_mismatch(ip_address: str, tz: str) -> bool:
    """Проверка несоответствия таймзоны и IP"""
    if is_dev_environment(ip_address):
        return False
    if not ip_address or not tz:
        return False

    try:
        response = reader_city.city(ip_address)
        city_tz = response.location.time_zone
        country = response.country.iso_code
        if not city_tz or city_tz.lower() != tz.lower():
            logging.warning(f"[ANTIFRAUD] IP {ip_address} TZ mismatch: {tz} vs {city_tz}")
            return True
    except Exception:
        logging.warning(f"[ANTIFRAUD] GeoIP lookup failed for IP {ip_address}")
        return True

    return False

def get_asn(ip_address: str) -> str:
    try:
        response = reader_asn.asn(ip_address)
        return response.autonomous_system_organization  # название провайдера
    except Exception:
        return "Unknown"



def log_event(reason: str, ip: str, data: dict, extra: dict = None):
    """Лог антифрод-событий в общий проектный лог"""
    logger.warning(
        f"[ANTIFRAUD] Blocked: {reason} | ip={ip} | device_id={data.get('device_id')} | extra={extra}"
    )



# def ip_timezone_mismatch(ip_address: str, tz: str) -> bool:
#     """Простая проверка: если таймзона пустая или странная — тоже флаг"""
#     if is_dev_environment(ip_address):
#         return False
#     if not ip_address or not tz:
#         return False
#     # TODO: можно интегрировать geoip2 для более точного сравнения
#     if tz.lower() in ["utc", "gmt", "etc/utc"] and not ip_address.startswith("127."):
#         return True
#     return False
