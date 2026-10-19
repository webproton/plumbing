"""
Загрузка по ссылкам, которые вводят пользователи (фиды поставщиков, фото товаров).

Защита от SSRF: только http(s), без логина в URL, хост должен разрешаться в публичный IP
(не localhost, не внутренняя сеть docker, не metadata-адреса облака). Редиректы проверяются
на каждом шаге, при смене хоста авторизация не пересылается. Размер ответа ограничен.
"""

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import requests
from django.utils.translation import gettext as _

USER_AGENT = "Mozilla/5.0 (compatible; PlumbingCatalogImport/1.0)"
TIMEOUT = (10, 60)  # соединение, чтение
MAX_REDIRECTS = 5
MAX_BYTES = 50 * 1024 * 1024


class FetchError(Exception):
    pass


@dataclass
class FetchResult:
    content: bytes
    content_type: str
    url: str
    encoding: str | None


def _is_public(ip: str) -> bool:
    addr = ipaddress.ip_address(ip.split("%", 1)[0])
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def check_url(url: str) -> None:
    """FetchError, если по ссылке нельзя ходить с сервера."""
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchError(_("Поддерживаются только ссылки http:// и https://"))
    if parts.username or parts.password:
        raise FetchError(_("Логин и пароль укажите в настройках доступа, а не в ссылке"))
    host = parts.hostname
    if not host:
        raise FetchError(_("Некорректная ссылка"))
    try:
        port = parts.port or (443 if parts.scheme == "https" else 80)
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, UnicodeError, ValueError):
        raise FetchError(_("Сервер {host} не найден").format(host=host)) from None
    if not infos or not all(_is_public(info[4][0]) for info in infos):
        raise FetchError(_("Адрес {host} недоступен для загрузки").format(host=host))


def _check_peer(response) -> None:
    """Повторная проверка фактического IP соединения (на случай подмены DNS между проверкой и запросом)."""
    try:
        sock = response.raw.connection.sock
        ip = sock.getpeername()[0]
    except (AttributeError, OSError, TypeError):
        return
    if not _is_public(ip):
        response.close()
        raise FetchError(_("Адрес недоступен для загрузки"))


def fetch(
    url: str,
    *,
    session: requests.Session | None = None,
    method: str = "GET",
    auth=None,
    headers: dict | None = None,
    params: dict | None = None,
    data=None,
    max_bytes: int = MAX_BYTES,
) -> FetchResult:
    session = session or requests.Session()
    origin = urlsplit(url).hostname
    headers = {"User-Agent": USER_AGENT, **(headers or {})}

    for _step in range(MAX_REDIRECTS + 1):
        check_url(url)
        same_host = urlsplit(url).hostname == origin
        try:
            response = session.request(
                method,
                url,
                params=params,
                data=data,
                auth=auth if same_host else None,
                headers=headers if same_host else {"User-Agent": USER_AGENT},
                timeout=TIMEOUT,
                stream=True,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            raise FetchError(_("Не удалось подключиться: {error}").format(error=exc.__class__.__name__)) from exc
        _check_peer(response)

        if response.is_redirect:
            location = response.headers.get("Location", "")
            response.close()
            url = urljoin(url, location)
            params = None
            if method != "GET" and response.status_code in (301, 302, 303):
                method, data = "GET", None
            continue

        if response.status_code >= 400:
            response.close()
            raise FetchError(_("Сервер ответил ошибкой {status}").format(status=response.status_code))

        chunks, size = [], 0
        try:
            for chunk in response.iter_content(64 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise FetchError(_("Файл больше {mb} МБ").format(mb=max_bytes // (1024 * 1024)))
                chunks.append(chunk)
        except requests.RequestException as exc:
            raise FetchError(_("Обрыв соединения при загрузке")) from exc
        finally:
            response.close()
        return FetchResult(
            content=b"".join(chunks),
            content_type=response.headers.get("Content-Type", ""),
            url=url,
            encoding=response.encoding if "charset" in response.headers.get("Content-Type", "") else None,
        )
    raise FetchError(_("Слишком много перенаправлений"))
