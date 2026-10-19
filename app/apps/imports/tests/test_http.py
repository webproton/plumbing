import socket

import pytest
from django.test import override_settings

from app.core import crypto
from app.core.http import FetchError, check_url, fetch


def _resolve_to(monkeypatch, mapping):
    def fake(host, port, *args, **kwargs):
        ip = mapping.get(host)
        if ip is None:
            raise socket.gaierror
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", fake)


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/feed.xml",
        "file:///etc/passwd",
        "http://127.0.0.1:8000/api/",
        "http://localhost/",
        "http://10.0.0.5/feed",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/",
        "http://user:pass@example.com/",
    ],
)
def test_check_url_blocks_internal_and_odd_urls(url):
    with pytest.raises(FetchError):
        check_url(url)


def test_check_url_blocks_hostname_resolving_to_private(monkeypatch):
    _resolve_to(monkeypatch, {"feed.evil.test": "192.168.1.10", "redis": "172.18.0.3"})
    for url in ("https://feed.evil.test/x.xml", "http://redis:6379/"):
        with pytest.raises(FetchError):
            check_url(url)


class _Resp:
    def __init__(self, status=200, headers=None, body=b"ok"):
        self.status_code, self.headers, self._body = status, headers or {}, body
        self.encoding = "utf-8"
        self.raw = None

    @property
    def is_redirect(self):
        return self.status_code in (301, 302, 303, 307, 308) and "Location" in self.headers

    def iter_content(self, size):
        yield self._body

    def close(self):
        pass


class _Session:
    def __init__(self, responses):
        self.responses, self.calls = list(responses), []

    def request(self, method, url, **kwargs):
        self.calls.append((method, url, kwargs))
        return self.responses.pop(0)


def test_fetch_redirect_to_internal_is_blocked(monkeypatch):
    _resolve_to(monkeypatch, {"supplier.test": "93.184.216.34"})
    session = _Session([_Resp(302, {"Location": "http://127.0.0.1/admin/"})])
    with pytest.raises(FetchError):
        fetch("https://supplier.test/feed", session=session)
    assert len(session.calls) == 1


def test_fetch_drops_auth_on_cross_host_redirect(monkeypatch):
    _resolve_to(monkeypatch, {"supplier.test": "93.184.216.34", "cdn.test": "93.184.216.35"})
    session = _Session([_Resp(302, {"Location": "https://cdn.test/f.xml"}), _Resp(200, body=b"<x/>")])
    result = fetch("https://supplier.test/feed", session=session, auth=("u", "p"), headers={"X-Key": "secret"})
    assert result.content == b"<x/>"
    first, second = session.calls
    assert first[2]["auth"] == ("u", "p") and first[2]["headers"]["X-Key"] == "secret"
    assert second[2]["auth"] is None and "X-Key" not in second[2]["headers"]


def test_fetch_size_limit_and_http_errors(monkeypatch):
    _resolve_to(monkeypatch, {"supplier.test": "93.184.216.34"})
    with pytest.raises(FetchError):
        fetch("https://supplier.test/big", session=_Session([_Resp(body=b"x" * 2000)]), max_bytes=1000)
    with pytest.raises(FetchError):
        fetch("https://supplier.test/missing", session=_Session([_Resp(404)]))


def test_crypto_roundtrip_and_key_change():
    token = crypto.encrypt("p@ss")
    assert token != "p@ss" and crypto.decrypt(token) == "p@ss"
    assert crypto.encrypt("") == "" and crypto.decrypt("") == ""
    with override_settings(SECRET_KEY="another-secret"), pytest.raises(ValueError):
        crypto.decrypt(token)
