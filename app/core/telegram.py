"""Отправка сообщений менеджерам в Telegram."""

import html
import logging

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

TIMEOUT = 5  # сек.; без таймаута зависший api.telegram.org блокировал воркер gunicorn


def esc(value) -> str:
    """Экранирует пользовательские данные для parse_mode=HTML."""
    return html.escape(str(value)) if value not in (None, "") else "—"


def next_manager_chat_id():
    """Round-robin по менеджерам; счётчик в общем кэше, а не в памяти процесса."""
    managers = settings.TELEGRAM_MANAGERS
    if not managers:
        return None
    key = "telegram:manager_rr"
    cache.add(key, 0, timeout=None)
    try:
        idx = cache.incr(key)
    except ValueError:
        idx = 0
    return managers[idx % len(managers)]


def send_message(chat_id, text) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token or not chat_id:
        logger.warning("Telegram не настроен (TOKEN_BOT / MANAGERS), сообщение не отправлено")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            timeout=TIMEOUT,
        )
    except requests.RequestException as exc:
        logger.error("Telegram недоступен: %s", exc)
        return False
    if not resp.ok:
        logger.error("Telegram вернул %s: %s", resp.status_code, resp.text[:200])
    return resp.ok
