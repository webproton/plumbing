from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import SellerViewSet, ShopViewSet

app_name = "sellers"

router = DefaultRouter()
router.register(r"sellers", SellerViewSet, basename="seller")
router.register(r"shops", ShopViewSet, basename="shop")

urlpatterns = [
    path("", include(router.urls)),
]
