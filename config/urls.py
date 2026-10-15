from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from dj_rest_auth.registration.views import VerifyEmailView

from app.core.views import health

# Все API-маршруты живут под /api/ (nginx проксирует /api/ на Django без переписывания пути).
api_urlpatterns = [
    path("health/", health, name="health"),
    path("", include("app.apps.products.urls", namespace="products")),
    path("orders/", include("app.apps.orders.urls", namespace="orders")),
    path("callback/", include("app.apps.callback.urls", namespace="callback")),
    path("sellers/", include("app.apps.sellers.urls", namespace="sellers")),
    path("warehouse/", include("app.apps.warehouse.urls", namespace="warehouse")),
    path("dj-rest-auth/", include("app.apps.accounts.urls", namespace="dj-rest-auth")),
    path("dj-rest-auth/registration/", include("dj_rest_auth.registration.urls")),
    path(
        "dj-rest-auth/registration/verify-email/",
        VerifyEmailView.as_view(),
        name="account_email_verification_sent",
    ),
]

urlpatterns = [
    path("api/", include(api_urlpatterns)),
    path("admin/", admin.site.urls),
    path("account/", include("allauth.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
