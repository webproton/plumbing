import hashlib
from typing import Dict, Optional


def normalize_string(value: Optional[str]) -> str:
    """Безопасное приведение строк к единому виду."""
    if not value:
        return ""
    return value.strip().lower()


def hash_canvas_data(canvas_data: str) -> str:
    """
    Хэширует строку canvas fingerprint (например, Base64-данные).
    Используется, если фронт отдаёт «сырые» данные.
    """
    return hashlib.sha256(canvas_data.encode("utf-8")).hexdigest()


def compare_fingerprints(fp1: Dict, fp2: Dict) -> bool:
    """
    Сравнение двух отпечатков. Минимальный набор:
    - Canvas hash
    - WebGL vendor/renderer
    - Audio hash
    """
    return (
        normalize_string(fp1.get("canvas_hash")) == normalize_string(fp2.get("canvas_hash"))
        and normalize_string(fp1.get("webgl_vendor")) == normalize_string(fp2.get("webgl_vendor"))
        and normalize_string(fp1.get("webgl_renderer")) == normalize_string(fp2.get("webgl_renderer"))
        and normalize_string(fp1.get("audio_hash")) == normalize_string(fp2.get("audio_hash"))
    )


def fingerprint_signature(event_data: Dict) -> str:
    """
    Формируем единый «отпечаток устройства» из нескольких полей.
    Подходит для дедупликации и поиска ботов.
    """
    raw = "|".join([
        normalize_string(event_data.get("browser")),
        normalize_string(event_data.get("browser_version")),
        normalize_string(event_data.get("os")),
        normalize_string(event_data.get("os_version")),
        normalize_string(event_data.get("device_model")),
        normalize_string(event_data.get("webgl_vendor")),
        normalize_string(event_data.get("webgl_renderer")),
        normalize_string(event_data.get("canvas_hash")),
        normalize_string(event_data.get("audio_hash")),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def is_suspicious_fingerprint(event_data: Dict) -> bool:
    """
    Простейшие эвристики:
    - Пустые fingerprint-поля
    - Подозрительные User-Agent + WebGL
    - Совпадение с "типичными ботами"
    """
    if not event_data.get("canvas_hash") or not event_data.get("webgl_vendor"):
        return True

    suspicious_vendors = ["swiftshader", "llvmpipe", "mesa", "unknown"]
    vendor = normalize_string(event_data.get("webgl_vendor"))
    if any(v in vendor for v in suspicious_vendors):
        return True

    return False

