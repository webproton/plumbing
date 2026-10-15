from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.apps.products.views import CategoryList, NewProducts, ProductListView, WishlistViewSet

app_name = "products"

router = DefaultRouter()
router.register(r"products", ProductListView, basename="product")

router.register(r"category", CategoryList, basename="category")


router.register(r"new_products", NewProducts, basename="new-products")

router.register(r"wishlist", WishlistViewSet, basename="wishlist")


urlpatterns = [
    path("", include(router.urls)),
]
