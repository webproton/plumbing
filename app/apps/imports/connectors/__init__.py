"""Коннекторы к источникам товаров. Выбор по ImportSource.kind."""

from .base import Connector, ConnectorError
from .web import ADAPTERS, SiteAdapter, register


def get_connector(source) -> Connector:
    from .api import ApiConnector
    from .feed import FeedConnector
    from .web import WebConnector

    classes = {"feed": FeedConnector, "api": ApiConnector, "web": WebConnector}
    try:
        return classes[source.kind](source)
    except KeyError:
        raise ConnectorError(f"unknown source kind {source.kind}") from None


__all__ = ["ADAPTERS", "Connector", "ConnectorError", "SiteAdapter", "get_connector", "register"]
