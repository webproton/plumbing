# apps/telemetry/services/scoring.py
from ..models import TelemetryEvent


def risk_score(event_data: dict) -> int:
    score = 0

    # 1. Подозрительный User-Agent
    ua = (event_data.get("browser") or "").lower()
    if ua in ["curl", "python", "bot"]:
        score += 50

    # 2. Слишком много событий от одного device_id
    device_id = event_data.get("device_id")
    if device_id:
        if TelemetryEvent.objects.filter(device_id=device_id).count() > 100:
            score += 30

    # 3. Подозрительное разрешение экрана
    if int(event_data.get("screen_width") or 0) < 200:
        score += 20

    # 4. Редкая комбинация timezone + язык
    tz = event_data.get("timezone")
    lang = event_data.get("lang")
    if tz == "UTC" and lang not in ["en-US", "ru-RU"]:
        score += 15

    return score
