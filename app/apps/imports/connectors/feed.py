from django.utils.translation import gettext as _

from app.core.http import fetch

from ..formats import parse_items
from .base import Connector, ConnectorError, FetchedCatalog


class FeedConnector(Connector):
    """Каталог одним файлом: по ссылке (YML/XML/CSV/Excel/JSON) или загруженный вручную."""

    def fetch(self) -> FetchedCatalog:
        s = self.source
        options = dict(s.options or {})
        if s.url:
            result = fetch(s.url, **self.request_kwargs())
            content = result.content
            options.setdefault("filename", result.url.rsplit("/", 1)[-1])
        elif s.file:
            content = self.read_uploaded_file()
            options.setdefault("filename", s.file.name)
        else:
            raise ConnectorError(_("Укажите ссылку на фид или загрузите файл"))
        items, info = parse_items(content, s.format, s.field_map, options)
        return FetchedCatalog(items, info)
