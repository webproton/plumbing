"""Настройки для тестов: не зависят от локального .env (кэш, почта, хэширование паролей)."""

from .settings import *  # noqa: F401,F403

DEBUG = False
# нейтральный язык: проверки текстов в тестах не зависят от переводов
LANGUAGE_CODE = "en-us"
LANGUAGES = [("en-us", "English"), ("uk", "Українська"), ("ru", "Русский")]
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]  # ускоряет тесты
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
TELEGRAM_BOT_TOKEN = ""
TELEGRAM_MANAGERS = []
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CREDENTIALS_KEY = ""

# Загрузки в тестах — во временную папку, а не в реальный MEDIA_ROOT
import tempfile  # noqa: E402

MEDIA_ROOT = tempfile.mkdtemp(prefix="plumb-test-media-")
PRIVATE_MEDIA_ROOT = tempfile.mkdtemp(prefix="plumb-test-private-")
