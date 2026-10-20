"""Публикация товара в канал Telegram (бот TOKEN_BOT должен быть администратором канала)."""

import logging

import requests
from django.conf import settings
from django.utils.translation import gettext as _

from app.core.telegram import esc

from .feeds import _absolute, _base

logger = logging.getLogger(__name__)
TIMEOUT = 10


class TelegramError(Exception):
    pass


def _money(value) -> str:
    return f"{value:,.2f}".replace(",", " ").replace(".", ",").replace(",00", "") + " ₴"


def caption(product) -> str:
    variants = [v for v in product.variants.all() if v.available and v.price is not None]
    v = min(variants, key=lambda x: x.price) if variants else None
    lines = [f"<b>{esc(product.name)}</b>"]
    if v:
        price = _money(v.price)
        prefix = _("от ") if len(variants) > 1 else ""
        if v.discount and v.original_price:
            lines.append(f"{prefix}<b>{price}</b>  <s>{_money(v.original_price)}</s>")
        else:
            lines.append(f"{prefix}<b>{price}</b>")
    if product.description:
        from .feeds import plain

        text = plain(product.description, 400)
        lines.append(esc(text if len(text) < 400 else text[:397] + "…"))
    lines.append(f'<a href="{_base()}/product/{product.slug}">{esc(_("Купить на сайте"))}</a>')
    return "\n\n".join(lines)


def post_product(product, channel: str) -> int | None:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        raise TelegramError(_("Не задан токен бота Telegram (TOKEN_BOT)"))
    if not channel:
        raise TelegramError(_("Укажите канал Telegram в настройках магазина"))
    photo = _absolute(product.photo.url) if product.photo else None
    text = caption(product)
    api = f"https://api.telegram.org/bot{token}"
    if photo and photo.startswith("https://"):
        payload, method = (
            {"chat_id": channel, "photo": photo, "caption": text[:1024], "parse_mode": "HTML"},
            "sendPhoto",
        )
    else:  # Telegram берёт фото только по публичной https-ссылке
        payload, method = {"chat_id": channel, "text": text, "parse_mode": "HTML"}, "sendMessage"
    try:
        data = requests.post(f"{api}/{method}", json=payload, timeout=TIMEOUT).json()
    except (requests.RequestException, ValueError) as exc:
        raise TelegramError(_("Telegram недоступен")) from exc
    if not data.get("ok"):
        raise TelegramError(_("Telegram: {error}").format(error=data.get("description", "")))
    return (data.get("result") or {}).get("message_id")
