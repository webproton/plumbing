from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import AdaptersView, ImportRunViewSet, ImportSourceViewSet, TemplateDownloadView

app_name = "imports"

router = DefaultRouter()
router.register("sources", ImportSourceViewSet, basename="source")
router.register("runs", ImportRunViewSet, basename="run")

urlpatterns = [
    path("template/", TemplateDownloadView.as_view(), name="template"),
    path("adapters/", AdaptersView.as_view(), name="adapters"),
    *router.urls,
]
