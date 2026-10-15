from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse


def health(request):
    """Проверка живости для docker/балансировщика: БД и кэш доступны."""
    checks = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
        checks["db"] = "ok"
    except Exception as exc:  # отдаём причину, чтобы было видно в docker ps / логах
        checks["db"] = f"error: {exc.__class__.__name__}"
    try:
        cache.set("health:ping", 1, timeout=5)
        checks["cache"] = "ok" if cache.get("health:ping") == 1 else "error"
    except Exception as exc:
        checks["cache"] = f"error: {exc.__class__.__name__}"
    healthy = all(v == "ok" for v in checks.values())
    return JsonResponse({"status": "ok" if healthy else "fail", **checks}, status=200 if healthy else 503)
