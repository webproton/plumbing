from dataclasses import dataclass, field

from django.utils.translation import gettext as _

MAX_FILE_BYTES = 50 * 1024 * 1024


class ConnectorError(Exception):
    pass


@dataclass
class FetchedCatalog:
    items: list
    info: dict = field(default_factory=dict)


class Connector:
    def __init__(self, source):
        self.source = source

    def fetch(self) -> FetchedCatalog:
        raise NotImplementedError

    def secret(self) -> str:
        try:
            return self.source.secret
        except ValueError:
            raise ConnectorError(_("Не удалось расшифровать пароль/ключ доступа — введите его заново")) from None

    def request_kwargs(self) -> dict:
        """Параметры авторизации для запроса к источнику (фид или API)."""
        s = self.source
        auth_type, login = s.auth_type, s.auth_login.strip()
        if auth_type == "basic":
            return {"auth": (login, self.secret())}
        if auth_type == "bearer":
            return {"headers": {"Authorization": f"Bearer {self.secret()}"}}
        if auth_type == "header":
            return {"headers": {login or "X-API-Key": self.secret()}}
        if auth_type == "query":
            return {"params": {login or "key": self.secret()}}
        return {}

    def read_uploaded_file(self) -> bytes:
        f = self.source.file
        if f.size > MAX_FILE_BYTES:
            raise ConnectorError(_("Файл больше {mb} МБ").format(mb=MAX_FILE_BYTES // (1024 * 1024)))
        with f.open("rb") as fh:
            return fh.read()
