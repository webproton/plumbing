from dj_rest_auth.registration.views import VerifyEmailView
from django.urls import include, path
from rest_framework.urlpatterns import format_suffix_patterns

from app.apps.accounts.views import CustomLoginView, CustomRegisterView

from .views import ProfileView

app_name = "dj-rest-auth"

urlpatterns = [
    path("profile/", ProfileView.as_view(), name="profile"),
    path("registration/", CustomRegisterView.as_view(), name="rest_register"),
    path("login/", CustomLoginView.as_view(), name="rest_login"),
    # Verify email
    path("registration/verify-email/", VerifyEmailView.as_view(), name="rest_verify_email"),
    path("account-confirm-email/<str:key>/", VerifyEmailView.as_view(), name="account_confirm_email"),
    path("account-confirm-email/", VerifyEmailView.as_view(), name="account_email_verification_sent"),
    # Подключаем стандартные dj-rest-auth пути для logout, password change/reset и т.д.
    path("", include("dj_rest_auth.urls")),
]

urlpatterns = format_suffix_patterns(urlpatterns)
