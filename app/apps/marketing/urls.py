from django.urls import path

from .seo import SitemapDataView
from .views import TelegramPublishView, feed_view

app_name = "marketing"

urlpatterns = [
    path("feeds/<str:token>/<str:name>", feed_view, name="feed"),
    path("marketing/telegram/products/<int:pk>/", TelegramPublishView.as_view(), name="telegram-publish"),
    path("seo/sitemap/", SitemapDataView.as_view(), name="seo-sitemap"),
]
