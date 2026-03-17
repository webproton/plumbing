from django.contrib import admin
from rest_framework.routers import DefaultRouter
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
# from django.contrib.sitemaps.views import sitemap
# from app.apps.products.sitemaps import ProductSitemap, CategorySitemap,BrandSitemap
from dj_rest_auth.registration.views import VerifyEmailView

# sitemaps_dict = {
#     'products': ProductSitemap,
#     'categories': CategorySitemap,
#     'brands': BrandSitemap,
# }

router = DefaultRouter()




urlpatterns = [
    path('admin/login/', admin.site.login, name='admin_login'),  # используем стандартный
    path("admin/", admin.site.urls),
    path("", include(router.urls)),
    path("account/", include("allauth.urls")),
    # Подключаем аккаунты через namespace "dj-rest-auth"
    path("api/dj-rest-auth/", include("apps.accounts.urls", namespace="dj-rest-auth")),

        # регистрация + verify-email
    path("api/dj-rest-auth/registration/", include("dj_rest_auth.registration.urls")),
    path(
        "api/dj-rest-auth/registration/verify-email/",
        VerifyEmailView.as_view(),
        name="account_email_verification_sent",
    ),


    # path("api/accounts/", include("apps.accounts.urls")),
    path('api/', include('app.apps.products.urls', namespace='products')),
    path("api/orders/", include("app.apps.orders.urls", namespace="orders")),
    # path("api/", include("app.apps.telemetry.urls")),
    # path('admin/', include('two_factor.urls', 'two_factor')), uncomment 

    path("callback/", include("app.apps.callback.urls")),

    # path('sitemap.xml', sitemap, {'sitemaps': sitemaps_dict}, name='sitemap'),
    

]
# urlpatterns += router.urls

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
