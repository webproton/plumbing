from django.urls import include, path
from rest_framework.routers import DefaultRouter

from app.apps.products.manage import ManageBrandsView, ManageProductViewSet, ManageVariantViewSet
from app.apps.products.views import CategoryList, NewProducts, ProductListView, WishlistViewSet

app_name = "products"

router = DefaultRouter()
router.register(r"products", ProductListView, basename="product")

router.register(r"category", CategoryList, basename="category")


router.register(r"new_products", NewProducts, basename="new-products")

router.register(r"wishlist", WishlistViewSet, basename="wishlist")

# редактор товаров кабинета продавца
router.register(r"manage/products", ManageProductViewSet, basename="manage-product")
router.register(r"manage/variants", ManageVariantViewSet, basename="manage-variant")
router.register(r"manage/brands", ManageBrandsView, basename="manage-brand")


urlpatterns = [
    path("", include(router.urls)),
]
