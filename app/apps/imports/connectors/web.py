"""
Сайты поставщиков, где каталог доступен только после входа (B2B-кабинеты).

Каждый сайт — свой адаптер (подкласс SiteAdapter, регистрируется через @register).
Готов универсальный адаптер form_login: вход через HTML-форму и скачивание прайса по ссылке
из кабинета — подходит для большинства B2B-порталов, где есть кнопка «Завантажити прайс».
Сайту без выгрузки нужен свой адаптер с разбором страниц каталога (catalog()).
"""

import html
import re
from urllib.parse import urljoin

import requests
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from app.core.http import fetch

from ..formats import parse_items
from .base import Connector, ConnectorError, FetchedCatalog

ADAPTERS: dict[str, type["SiteAdapter"]] = {}


def register(cls):
    ADAPTERS[cls.code] = cls
    return cls


class SiteAdapter:
    code = ""
    title = ""
    description = ""
    # настройки, которые адаптер читает из source.options: {имя: подсказка}
    option_fields: dict = {}

    def __init__(self, source, connector: Connector):
        self.source = source
        self.connector = connector
        self.session = requests.Session()

    def absolute(self, url: str) -> str:
        base = self.source.url or (self.source.options or {}).get("login_url", "")
        return urljoin(base, url)

    def get(self, url: str, **kwargs):
        return fetch(self.absolute(url), session=self.session, **kwargs)

    def post(self, url: str, data: dict, **kwargs):
        return fetch(self.absolute(url), session=self.session, method="POST", data=data, **kwargs)

    def option(self, name: str, default=None, required=False):
        value = (self.source.options or {}).get(name, default)
        if required and not value:
            raise ConnectorError(_("Не заполнена настройка «{name}»").format(name=name))
        return value

    def login(self) -> None:
        raise NotImplementedError

    def catalog(self) -> FetchedCatalog:
        raise NotImplementedError


def _input_value(page: str, name: str) -> str:
    for tag in re.findall(r"<input[^>]+>", page, flags=re.IGNORECASE):
        if re.search(rf"""name\s*=\s*["']{re.escape(name)}["']""", tag):
            match = re.search(r"""value\s*=\s*["']([^"']*)["']""", tag)
            return html.unescape(match.group(1)) if match else ""
    return ""


@register
class FormLoginAdapter(SiteAdapter):
    code = "form_login"
    title = gettext_lazy("Вход через форму + скачивание прайса")
    description = gettext_lazy(
        "Открывает страницу входа, отправляет логин и пароль, затем скачивает файл прайса по ссылке из кабинета."
    )
    option_fields = {
        "login_url": gettext_lazy("Страница входа"),
        "login_post_url": gettext_lazy("Куда отправляется форма (если отличается)"),
        "username_field": gettext_lazy("Имя поля логина (login, email, username…)"),
        "password_field": gettext_lazy("Имя поля пароля"),
        "csrf_field": gettext_lazy("Имя скрытого поля защиты формы (csrf), если есть"),
        "export_url": gettext_lazy("Ссылка на скачивание прайса после входа"),
        "logged_in_marker": gettext_lazy("Текст, который виден только после входа (например «Выйти»)"),
    }

    def login(self):
        login_url = self.option("login_url", required=True)
        password_field = self.option("password_field", "password")
        page = self.get(login_url).content.decode("utf-8", errors="replace")
        form = {
            self.option("username_field", "login"): self.source.auth_login,
            password_field: self.connector.secret(),
            **(self.option("extra_fields", {}) or {}),
        }
        csrf_field = self.option("csrf_field", "")
        if csrf_field:
            form[csrf_field] = _input_value(page, csrf_field)
        response = self.post(self.option("login_post_url") or login_url, form)
        body = response.content.decode("utf-8", errors="replace")
        marker = self.option("logged_in_marker", "")
        failed = (
            marker not in body if marker else re.search(rf"""name\s*=\s*["']{re.escape(password_field)}["']""", body)
        )
        if failed:
            raise ConnectorError(_("Не удалось войти на сайт поставщика — проверьте логин и пароль"))

    def catalog(self):
        result = self.get(self.option("export_url", required=True))
        options = {**(self.source.options or {}), "filename": result.url.rsplit("/", 1)[-1]}
        items, info = parse_items(result.content, self.source.format, self.source.field_map, options)
        return FetchedCatalog(items, info)


class WebConnector(Connector):
    def fetch(self) -> FetchedCatalog:
        adapter_cls = ADAPTERS.get(self.source.adapter)
        if adapter_cls is None:
            raise ConnectorError(
                _("Адаптер «{adapter}» для сайта поставщика не подключён").format(adapter=self.source.adapter or "—")
            )
        if not self.source.auth_login:
            raise ConnectorError(_("Укажите логин для входа на сайт поставщика"))
        adapter = adapter_cls(self.source, self)
        adapter.login()
        return adapter.catalog()
