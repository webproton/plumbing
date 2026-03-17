from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework.urlpatterns import format_suffix_patterns
from app.apps.products.views import ProductListView, CategoryList, NewProducts,  WishlistViewSet
from django.conf import settings
from django.conf.urls.static import static

app_name = "apps.products"

router = DefaultRouter()
router.register(r"products", ProductListView, basename="product")

router.register(r"category", CategoryList, basename="category")

# router.register(r"brands", BrandList, basename="brands")

router.register(r"new_products", NewProducts, basename="new-products")

router.register(r'wishlist', WishlistViewSet, basename='wishlist')


urlpatterns = [
    
     path("", include(router.urls)),
]
