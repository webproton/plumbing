from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from dj_rest_auth.registration.views import VerifyEmailView

# Создаем основной роутер для DRF (если нужен)
router = DefaultRouter()

# ===========================
# Подключение приложений через namespace/routers
# ===========================

# Callback
urlpatterns = [
    path("request/", include("app.apps.callback.urls", namespace="app.apps.callback")),
    path("site-settings/", include("app.apps.callback.urls", namespace="app.apps.callback")),
]

# Sellers
urlpatterns += [
    path("sellers/", include("app.apps.sellers.urls", namespace="app.apps.sellers")),
]

# Telemetry
urlpatterns += [
    path("telemetry/", include("app.apps.telemetry.urls", namespace="app.apps.telemetry")),
]

# Products
urlpatterns += [
    path("products/", include("app.apps.products.urls", namespace="app.apps.products")),
]

# Orders
urlpatterns += [
    path("orders/", include("app.apps.orders.urls", namespace="app.apps.orders")),
]

# Warehouse (includes suppliers, warehouses, stock-movements, inventory-documents)
urlpatterns += [
    path("warehouse/", include("app.apps.warehouse.urls", namespace="app.apps.warehouse")),
]

# ===========================
# Admin
# ===========================
urlpatterns += [
    path('admin/login/', admin.site.login, name='admin_login'),
    path("admin/", admin.site.urls),
]

# ===========================
# Auth (allauth / dj-rest-auth)
# ===========================
urlpatterns += [
    path("account/", include("allauth.urls")),
    path("api/dj-rest-auth/registration/", include("dj_rest_auth.registration.urls")),
    path(
        "api/dj-rest-auth/registration/verify-email/",
        VerifyEmailView.as_view(),
        name="account_email_verification_sent",
    ),
]

# ===========================
# Статика и медиа
# ===========================
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
