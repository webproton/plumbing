from django.urls import path

from .views import TelegramPublishView, feed_view

app_name = "marketing"

urlpatterns = [
    path("feeds/<str:token>/<str:name>", feed_view, name="feed"),
    path("marketing/telegram/products/<int:pk>/", TelegramPublishView.as_view(), name="telegram-publish"),
]
