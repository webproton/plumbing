import logging

from dj_rest_auth.forms import AllAuthPasswordResetForm
from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer, PasswordResetSerializer, UserDetailsSerializer
from django.contrib.auth import get_user_model
from django.utils.translation import gettext as _
from rest_framework import serializers

from app.apps.accounts.models import Profile

User = get_user_model()
logger = logging.getLogger(__name__)


# pylint: disable=W0223

ALLOWED_DOMAINS = [
    "gmail.com",  # Google
    "yahoo.com",  # Yahoo
    "outlook.com",  # Microsoft
    "hotmail.com",  # Microsoft
    "live.com",  # Microsoft
    "icloud.com",  # Apple
    "aol.com",  # AOL (USA)
    "mail.com",  # Mail.com
    "protonmail.com",  # Швейцария
    "gmx.com",  # Германия (GMX)
    "zoho.com",  # Zoho Mail (международный бизнес)
    "tutanota.com",  # Германия (защищённая почта)
    # Украина
    "ukr.net",
    "i.ua",
    "meta.ua",
    "bigmir.net",
    "email.ua",
    "online.ua",
    "gmail.com.ua",
    # Европейские
    "orange.fr",  # Франция
    "wanadoo.fr",  # Франция
    "web.de",  # Германия
    "freenet.de",  # Германия
    "libero.it",  # Италия
    "t-online.de",  # Германия
]

FORBIDDEN_USERNAMES = ["admin", "root", "superuser"]


class CustomRegisterSerializer(RegisterSerializer):
    """override RegisterSerializer for custom registration"""

    username = None

    email = serializers.EmailField(required=True)
    password1 = serializers.CharField(write_only=True)

    def save(self, request):

        user = super().save(request)  # пароль хранится только в User (хэш); в Profile — никогда
        Profile.objects.update_or_create(user=user, defaults={"email": user.email})
        logger.info(f"[PROFILE] Профиль создан/обновлён для пользователя {user.email}")
        return user

    def validate_email(self, value):
        domain = value.split("@")[-1].lower()
        if domain not in ALLOWED_DOMAINS:
            logger.warning(f"[EMAIL] Недопустимый домен: {domain}")
            raise serializers.ValidationError(_("Регистрация доступна только с популярных почтовых сервисов."))

        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(_("Пользователь с таким email уже существует."))

        return value

    def validate_password1(self, value):
        if "password" in value:
            raise serializers.ValidationError(_("Пароль не должен содержать слово «password»"))
        return value


class CustomLoginSerializer(LoginSerializer):
    """Вход по email. Проверку пароля и подтверждения email выполняет базовый LoginSerializer."""

    username = None
    email = serializers.EmailField(required=True)


class UserSerializer(UserDetailsSerializer):
    """User serializer"""

    class Meta:
        """change email on  readonly option"""

        model = User
        fields = (
            "email",
            "first_name",
            "last_name",
            "middle_name",
            "phone_number",
            "city",
            "address",
            "gender",
            "birth_date",
            "avatar",
        )
        extra_kwargs = {
            "email": {"read_only": True},  # изменение email идёт отдельно
        }


class FrontendPasswordResetForm(AllAuthPasswordResetForm):
    """
    Письмо сброса пароля со ссылкой на страницу витрины /reset-password/confirm?uid=…&token=….
    Стандартная форма строила ссылку через несуществующий маршрут Django (password_reset_confirm) и падала.
    """

    def save(self, request, **kwargs):
        from allauth.account.adapter import get_adapter
        from allauth.account.forms import default_token_generator
        from allauth.account.utils import user_pk_to_url_str
        from django.conf import settings
        from django.contrib.sites.shortcuts import get_current_site

        token_generator = kwargs.get("token_generator", default_token_generator)
        for user in self.users:
            uid, token = user_pk_to_url_str(user), token_generator.make_token(user)
            url = f"{settings.FRONTEND_URL.rstrip('/')}/reset-password/confirm?uid={uid}&token={token}"
            context = {
                "current_site": get_current_site(request),
                "user": user,
                "password_reset_url": url,
                "request": request,
            }
            get_adapter(request).send_mail("account/email/password_reset_key", self.cleaned_data["email"], context)
        return self.cleaned_data["email"]


class CustomPasswordResetSerializer(PasswordResetSerializer):
    @property
    def password_reset_form_class(self):
        return FrontendPasswordResetForm
