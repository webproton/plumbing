from dj_rest_auth.registration.serializers import RegisterSerializer
from dj_rest_auth.serializers import LoginSerializer, UserDetailsSerializer
# from captcha.fields import ReCaptchaField
# from captcha.widgets import ReCaptchaV2Checkbox
from app.apps.accounts.models import Profile
from django.contrib.auth import get_user_model
from rest_framework import serializers
from django.conf import settings
User = get_user_model()
from django.contrib.auth import authenticate

import logging
logger = logging.getLogger(__name__)



# pylint: disable=W0223

ALLOWED_DOMAINS = [
    "gmail.com",           # Google
    "yahoo.com",           # Yahoo
    "outlook.com",         # Microsoft
    "hotmail.com",         # Microsoft
    "live.com",            # Microsoft
    "icloud.com",          # Apple
    "aol.com",             # AOL (USA)
    "mail.com",            # Mail.com
    "protonmail.com",      # Швейцария
    "gmx.com",             # Германия (GMX)
    "zoho.com",            # Zoho Mail (международный бизнес)
    "tutanota.com",        # Германия (защищённая почта)

    # Европейские
    "orange.fr",           # Франция
    "wanadoo.fr",          # Франция
    "web.de",              # Германия
    "freenet.de",          # Германия
    "libero.it",           # Италия
    "t-online.de",         # Германия



]

FORBIDDEN_USERNAMES = ["admin", "root", "superuser"]

class CustomRegisterSerializer(RegisterSerializer):
    """override RegisterSerializer for custom registration"""

    username = None
    def __init__(self, *args, **kwargs):
        logger.info("✅ CustomRegisterSerializer инициализирован")
        super().__init__(*args, **kwargs)
        
    email = serializers.EmailField(required=True)
    # username = serializers.CharField(required=True)
    password1 = serializers.CharField(write_only=True)
    #captcha = serializers.CharField(write_only=True)  # сюда придет token с фронта

    # def validate_captcha(self, value):
    # На фронте: вставляешь виджет reCAPTCHA и отправляешь токен в поле captcha.
    #     import requests
    #     secret = settings.RECAPTCHA_PRIVATE_KEY
    #     resp = requests.post(
    #         "https://www.google.com/recaptcha/api/siteverify",
    #         data={"secret": secret, "response": value}
    #     )
    #     result = resp.json()
    #     if not result.get("success"):
    #         raise serializers.ValidationError("Captcha не пройдена")
    #     return value

    def save(self, request):

        user = super().save(request)  # создаём пользователя через базовый сериализатор
        
        # создаём или обновляем профиль
        Profile.objects.update_or_create(
            user=user,
            defaults={
                "email": user.email,
                "password": self.validated_data["password1"]   # хэшируем пароль
            }
        )
        logger.info(f"[PROFILE] Профиль создан/обновлён для пользователя {user.email}")
        return user

    def validate_email(self, value):
        logger.debug(f"[EMAIL] Введено: {value}")
        domain = value.split("@")[-1].lower()
        if domain not in ALLOWED_DOMAINS:
            logger.warning(f"[EMAIL] Недопустимый домен: {domain}")
            raise serializers.ValidationError("Регистрация доступна только с популярных почтовых сервисов.")
        
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Пользователь с таким email уже существует.")
        
        return value
    
    def validate_password1(self, value):
        # например, запретить использовать слово "admin"
        if "password" in value:
            raise serializers.ValidationError("Нельзя использовать 'password' в имени")
        return value

    


class CustomLoginSerializer(LoginSerializer):
    username = None
    email = serializers.EmailField(required=True)
    # Указываем, что USERNAME_FIELD для модели — email
    username_field = User.USERNAME_FIELD


    """override LoginSerializer for custom sign in"""
    def __init__(self, *args, **kwargs):
        logger.info("✅ CustomLoginSerializer инициализирован")
        super().__init__(*args, **kwargs)

    def validate(self, attrs):
        # вызов базовой валидации LoginSerializer (он сам создаёт user)
        attrs = super().validate(attrs)
        email = attrs.get('email')
        password = attrs.get('password')
        if not email or not password:
            raise serializers.ValidationError("Email и пароль обязательны")

        if "password" in password.lower():
            raise serializers.ValidationError("Нельзя использовать 'password' в пароле")

        # Используем стандартную функцию authenticate с email вместо username
        user = authenticate(username=email, password=password)
        if not user:
            raise serializers.ValidationError("Неверные email или пароль")

        attrs['user'] = user
        return attrs


class UserSerializer(UserDetailsSerializer):
    """User serializer"""
    class Meta:
        """change email on  readonly option"""
        model = User
        fields = (
            "email", "first_name", "last_name", "middle_name", "phone_number",
            "city", "address", "gender", "birth_date", "avatar"
        )
        extra_kwargs = {
            "email": {"read_only": True}, # изменение email идёт отдельно
        }
