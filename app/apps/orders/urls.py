from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .manage import ManageOrderViewSet
from .views import CartViewSet, OrderListView, OrderView

app_name = "orders"

router = DefaultRouter()

router.register(r"history", OrderListView, basename="user-orders")
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"order-create", OrderView, basename="order-create")
router.register(r"manage", ManageOrderViewSet, basename="manage-order")


urlpatterns = [
    path("", include(router.urls)),
]
