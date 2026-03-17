from django.urls import path,include
from rest_framework.routers import DefaultRouter
from .views import *


app_name = "apps.orders"

router = DefaultRouter()

router.register(r"history", OrderListView, basename="user-orders")
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"order-create", OrderView, basename="order-create")
# router.register(r'history', UserOrdersView, basename='user-orders')


urlpatterns = [
    path("", include(router.urls)),

    # path('orders/<int:pk>/cancel/', CancelOrderView.as_view(), name='order-cancel'),

]

