"""
Django settings for the plumbing project.

Все значения, зависящие от окружения, читаются из переменных окружения / .env.
Значения по умолчанию безопасны для production (DEBUG выключен, cookie secure),
для локальной разработки переопределяются в .env (см. .env.example).
"""

import sys
from datetime import timedelta
from pathlib import Path

import environ
from corsheaders.defaults import default_headers

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent
# Пакет `parsers` импортируется как top-level модуль.
sys.path.insert(0, str(BASE_DIR / "app"))

env = environ.Env()
env_file = BASE_DIR / ".env"
if env_file.exists():
    environ.Env.read_env(str(env_file))


# ==============================
# Core
# ==============================
SECRET_KEY = env("SECRET_KEY")
DEBUG = env.bool("DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])
# Внутренние имена сервисов (в docker витрина ходит в Django по http://app:8000 — Host: app)
ALLOWED_HOSTS += env.list("DJANGO_INTERNAL_HOSTS", default=[])

FRONTEND_URL = env("FRONTEND_URL", default="") or "http://localhost:3000"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
SITE_ID = 1

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
    "corsheaders",
    "rest_framework",
    "rest_framework.authtoken",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "dj_rest_auth",
    "dj_rest_auth.registration",
    "django_filters",
    "axes",
    "app.apps.accounts",
    "app.apps.products",
    "app.apps.orders",
    "app.apps.callback",
    "app.apps.sellers",
    "app.apps.warehouse",
    "app.apps.imports",
]

MIDDLEWARE = [
    "app.core.middleware.RealIPMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    # язык ответа по Accept-Language (витрина присылает uk-UA / ru-UA)
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # AxesMiddleware должен быть последним
    "axes.middleware.AxesMiddleware",
]

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# ==============================
# Database / cache
# ==============================
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", default="plumbingrestapi"),
        "USER": env("POSTGRES_USER", default="postgres"),
        "PASSWORD": env("POSTGRES_PASSWORD", default=""),
        "HOST": env("POSTGRES_HOST", default="localhost"),
        "PORT": env.int("POSTGRES_PORT", default=5432),
        "CONN_MAX_AGE": env.int("DB_CONN_MAX_AGE", default=60),
    }
}

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/1")
CACHES = {"default": env.cache_url("CACHE_URL", default=REDIS_URL.replace("redis://", "rediscache://", 1))}


# ==============================
# Auth
# ==============================
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

AUTHENTICATION_BACKENDS = (
    "axes.backends.AxesStandaloneBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
)

AXES_FAILURE_LIMIT = env.int("AXES_FAILURE_LIMIT", default=10)
AXES_COOLOFF_TIME = 1  # час
# Блокируем по связке пользователь+IP, чтобы один атакующий не блокировал вход всем.
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
# REMOTE_ADDR уже исправлен RealIPMiddleware; X-Forwarded-For от клиента не доверяем.
AXES_IPWARE_META_PRECEDENCE_ORDER = ("REMOTE_ADDR",)

ACCOUNT_ADAPTER = "app.apps.accounts.adapters.CustomAccountAdapter"
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = "email"
ACCOUNT_CONFIRM_EMAIL_ON_GET = False
ACCOUNT_EMAIL_VERIFICATION = env("ACCOUNT_EMAIL_VERIFICATION", default="mandatory")
ACCOUNT_DEFAULT_HTTP_PROTOCOL = "http" if DEBUG else "https"
EMAIL_CONFIRMATION_AUTHENTICATED_REDIRECT_URL = f"{FRONTEND_URL}/confirmed/"
EMAIL_CONFIRMATION_ANONYMOUS_REDIRECT_URL = f"{FRONTEND_URL}/confirmed/"
LOGIN_REDIRECT_URL = f"{FRONTEND_URL}/"
LOGIN_URL = "/admin/login/"

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=30),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

REST_AUTH = {
    "USE_JWT": True,
    # TODO(frontend-v2): перейти на HttpOnly refresh-cookie (JWT_AUTH_HTTPONLY=True),
    # сейчас старый фронт берёт оба токена из тела ответа и хранит в localStorage.
    "JWT_AUTH_COOKIE": None,
    "JWT_AUTH_REFRESH_COOKIE": None,
    "JWT_AUTH_HTTPONLY": False,
    "REGISTER_SERIALIZER": "app.apps.accounts.serializers.CustomRegisterSerializer",
    "PASSWORD_RESET_CONFIRM_URL": f"{FRONTEND_URL}/reset-password/confirm?uid={{uid}}&token={{token}}",
    "EMAIL_VERIFICATION_URL": f"{FRONTEND_URL}/confirm-email/{{key}}/",
}


# ==============================
# DRF
# ==============================
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "EXCEPTION_HANDLER": "app.core.exceptions.api_exception_handler",
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
        "rest_framework.parsers.FormParser",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    # 0 = брать IP из REMOTE_ADDR (его исправляет RealIPMiddleware), а не из X-Forwarded-For клиента.
    "NUM_PROXIES": 0,
    "DEFAULT_THROTTLE_RATES": {
        "anon": env("THROTTLE_ANON", default="120/min"),
        "user": env("THROTTLE_USER", default="300/min"),
    },
}


# ==============================
# CORS / CSRF / security
# ==============================
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[FRONTEND_URL])
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [*default_headers, "x-device-id", "x-session-id"]
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[FRONTEND_URL])

# За nginx: доверяем X-Real-IP / X-Forwarded-Proto только если явно включено.
TRUSTED_PROXY = env.bool("TRUSTED_PROXY", default=False)
if TRUSTED_PROXY:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = env.bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = env.bool("CSRF_COOKIE_SECURE", default=not DEBUG)
SECURE_SSL_REDIRECT = env.bool("SECURE_SSL_REDIRECT", default=False)  # редирект делает nginx
SECURE_HSTS_SECONDS = env.int("SECURE_HSTS_SECONDS", default=0 if DEBUG else 31536000)
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024


# ==============================
# i18n
# ==============================
LANGUAGE_CODE = "uk"
LANGUAGES = [("uk", "Українська"), ("ru", "Русский")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "Europe/Kyiv"
USE_I18N = True
USE_TZ = True


# ==============================
# Static / media
# ==============================
STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# Файлы накладных и сгенерированные PDF — вне публичного MEDIA_ROOT, отдаются только через API.
PRIVATE_MEDIA_ROOT = Path(env("PRIVATE_MEDIA_ROOT", default=str(BASE_DIR / "private_media")))


# ==============================
# Email
# ==============================
EMAIL_BACKEND = env(
    "EMAIL_BACKEND",
    default="django.core.mail.backends.console.EmailBackend"
    if DEBUG
    else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST = env("EMAIL_HOST", default="")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
EMAIL_TIMEOUT = 10
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default=EMAIL_HOST_USER or "noreply@localhost")


# ==============================
# Integrations
# ==============================
TELEGRAM_BOT_TOKEN = env("TOKEN_BOT", default="")
TELEGRAM_MANAGERS = [m.strip() for m in env.list("MANAGERS", default=[]) if m.strip()]
# Ключ шифрования доступов к сайтам поставщиков. Пусто — выводится из SECRET_KEY
# (тогда при смене SECRET_KEY пароли поставщиков придётся ввести заново).
CREDENTIALS_KEY = env("CREDENTIALS_KEY", default="")
# Разбор накладных через Claude (запасной вариант): off — выключен; manual — по кнопке;
# auto — ещё и автоматически, если накладная не разобралась (скан, фото, не сходится арифметика)
INVOICE_AI_MODE = env("INVOICE_AI_MODE", default="off")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
INVOICE_AI_MODEL = env("INVOICE_AI_MODEL", default="claude-opus-5-5")


# ==============================
# Celery (фоновые задачи: импорт, синхронизация поставщиков, уведомления)
# ==============================
# Отдельная БД Redis: cache.clear() кэша не должен стирать очередь задач
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="redis://localhost:6379/2")
CELERY_TASK_IGNORE_RESULT = True  # результаты задачи пишут в свои модели (ImportRun)
# True — выполнять задачи сразу в процессе запроса (без воркера): тесты, разработка
CELERY_TASK_ALWAYS_EAGER = env.bool("CELERY_TASK_ALWAYS_EAGER", default=False)
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
CELERY_TASK_TIME_LIMIT = 30 * 60
CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BEAT_SCHEDULE = {
    # раз в 5 минут ставит в очередь источники, у которых подошло время синхронизации
    "imports-sync-due-sources": {"task": "imports.sync_due_sources", "schedule": 300.0},
}


# ==============================
# Logging (stdout — собирается docker/journald)
# ==============================
LOG_LEVEL = env("LOG_LEVEL", default="INFO")
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "[{levelname}] {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "stream": sys.stdout, "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "app": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
        "parsers": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False},
    },
}
