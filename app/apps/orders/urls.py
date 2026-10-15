from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import CartViewSet, OrderListView, OrderView


app_name = "orders"

router = DefaultRouter()

router.register(r"history", OrderListView, basename="user-orders")
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"order-create", OrderView, basename="order-create")


urlpatterns = [
    path("", include(router.urls)),


]

