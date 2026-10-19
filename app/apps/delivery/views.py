"""Публичные справочники Новой Почты для оформления заказа (кэшируются)."""

from django.utils.translation import get_language
from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from app.apps.callback.models import SiteSettings

from . import novaposhta as np


class _NPView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "novaposhta"

    def handle_np(self, fn):
        try:
            return Response(fn())
        except np.NovaPoshtaError as exc:
            return Response({"detail": str(exc)}, status=503)


class CitiesView(_NPView):
    """GET ?q=Київ → [{ref, name, label, warehouses}]"""

    def get(self, request):
        return self.handle_np(lambda: np.search_cities(request.query_params.get("q", "")[:60]))


class WarehousesView(_NPView):
    """GET ?city=<CityRef>&q=12 → [{ref, number, name, kind, max_weight}]"""

    def get(self, request):
        city = request.query_params.get("city", "")
        if len(city) != 36:
            return Response([])
        lang = "ru" if (get_language() or "").startswith("ru") else "uk"
        return self.handle_np(lambda: np.warehouses(city, request.query_params.get("q", "")[:60], lang))


class EstimateView(_NPView):
    """GET ?city=<CityRef>&cost=1500&weight=2 → {cost, date}; {} — если не задан город отправителя."""

    def get(self, request):
        city = request.query_params.get("city", "")
        sender = SiteSettings.current().np_sender_city_ref
        if len(city) != 36 or not sender:
            return Response({})
        try:
            cost = float(request.query_params.get("cost") or 0)
            weight = float(request.query_params.get("weight") or 1)
        except ValueError:
            cost, weight = 0, 1
        return self.handle_np(lambda: np.estimate(city, cost, weight, sender))
