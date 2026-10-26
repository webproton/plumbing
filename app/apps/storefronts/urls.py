from django.urls import path

from .views import CurrentStorefrontView, DemoStorefrontsView

app_name = "storefronts"

urlpatterns = [
    path("current/", CurrentStorefrontView.as_view(), name="current"),
    path("demo/", DemoStorefrontsView.as_view(), name="demo"),
]
