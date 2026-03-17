from django.urls import path,include
from .views import TelemetryEventViewSet,TelemetryCollectAPIView

from rest_framework.routers import DefaultRouter

app_name = "apps.telemetry"

router = DefaultRouter()


router.register(r"events", TelemetryEventViewSet, basename="telemetry-event")

urlpatterns = [
    path("", include(router.urls)),
    path('telemetry/collect/', TelemetryCollectAPIView.as_view(), name='telemetry-collect'),
]