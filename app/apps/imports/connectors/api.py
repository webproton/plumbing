from django.utils.translation import gettext as _

from app.core.http import fetch

from ..formats import FormatError, dedupe, json_records, parse_records
from .base import Connector, ConnectorError, FetchedCatalog

MAX_PAGES = 500


class ApiConnector(Connector):
    """
    JSON API поставщика. options:
      items_path   — путь к списку товаров в ответе («data.items»); пусто — найдётся сам
      page_param   — имя параметра страницы («page»); пусто — одна страница
      page_start   — номер первой страницы (по умолчанию 1)
      page_size_param / page_size — если API требует размер страницы
      max_pages    — ограничение числа страниц (по умолчанию 100)
    field_map — наше поле → путь в объекте товара («prices.retail»).
    """

    def fetch(self) -> FetchedCatalog:
        s, opts = self.source, self.source.options or {}
        if not s.url:
            raise ConnectorError(_("Укажите адрес API"))
        kwargs = self.request_kwargs()
        base_params = dict(kwargs.pop("params", {}))
        headers = {"Accept": "application/json", **kwargs.pop("headers", {})}
        page_param = opts.get("page_param", "")
        page = int(opts.get("page_start", 1))
        max_pages = min(int(opts.get("max_pages", 100)), MAX_PAGES) if page_param else 1
        if opts.get("page_size_param") and opts.get("page_size"):
            base_params[opts["page_size_param"]] = opts["page_size"]

        records = []
        for _n in range(max_pages):
            params = {**base_params, **({page_param: page} if page_param else {})}
            result = fetch(s.url, params=params or None, headers=headers, **kwargs)
            batch = json_records(result.content, opts.get("items_path", ""))
            if not batch:
                break
            records.extend(batch)
            page += 1
        if not records:
            raise FormatError(_("API вернуло пустой список товаров"))
        items, info = parse_records(records, s.field_map or {})
        info["format"] = "json"
        return FetchedCatalog(dedupe(items, info), info)
