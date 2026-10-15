from django.urls import path

from . import views

app_name = "callback"

urlpatterns = [
    path("request/", views.callback_request, name="callback_request"),
    path("site-settings/", views.SiteSettingsView.as_view(), name="site-settings"),
]
