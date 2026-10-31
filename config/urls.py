from dj_rest_auth.registration.views import VerifyEmailView
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from app.apps.products.thumbs import media_thumb
from app.core.views import health

# Все API-маршруты живут под /api/ (nginx проксирует /api/ на Django без переписывания пути).
api_urlpatterns = [
    path("health/", health, name="health"),
    path("", include("app.apps.products.urls", namespace="products")),
    path("orders/", include("app.apps.orders.urls", namespace="orders")),
    path("callback/", include("app.apps.callback.urls", namespace="callback")),
    path("sellers/", include("app.apps.sellers.urls", namespace="sellers")),
    path("warehouse/", include("app.apps.warehouse.urls", namespace="warehouse")),
    path("imports/", include("app.apps.imports.urls", namespace="imports")),
    path("delivery/", include("app.apps.delivery.urls", namespace="delivery")),
    path("storefronts/", include("app.apps.storefronts.urls", namespace="storefronts")),
    path("", include("app.apps.marketing.urls", namespace="marketing")),
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
    # уменьшенные копии фото: nginx отдаёт готовые сам, сюда — только первый запрос (app/apps/products/thumbs.py)
    path("media/thumbs/<int:width>/<path:path>", media_thumb, name="media_thumb"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
