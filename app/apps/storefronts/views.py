from rest_framework import permissions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Storefront
from .resolve import current


class StorefrontSerializer(serializers.ModelSerializer):
    class Meta:
        model = Storefront
        fields = [
            "slug",
            "name",
            "tagline",
            "tagline_ru",
            "verticals",
            "brand_color",
            "logo",
            "phone",
            "email",
            "address",
            "telegram_bot",
            "is_demo",
        ]


class CurrentStorefrontView(APIView):
    """GET — витрина запроса (заголовок X-Storefront, ?storefront= или домен); null — общий магазин."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        storefront = current(request)
        data = StorefrontSerializer(storefront, context={"request": request}).data if storefront else None
        return Response({"storefront": data})


class DemoStorefrontsView(APIView):
    """GET — демо-витрины для показа клиентам (страница /demo на сайте)."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        items = Storefront.objects.filter(is_active=True, is_demo=True)
        return Response(StorefrontSerializer(items, many=True, context={"request": request}).data)
