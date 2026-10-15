"""Настройки для тестов: не зависят от локального .env (кэш, почта, хэширование паролей)."""

from .settings import *  # noqa: F401,F403

DEBUG = False
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # ускоряет тесты
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_MANAGERS = []

# Загрузки в тестах — во временную папку, а не в реальный MEDIA_ROOT
import tempfile  # noqa: E402

MEDIA_ROOT = tempfile.mkdtemp(prefix="plumb-test-media-")
PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="plumb-test-private-")
