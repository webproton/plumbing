from django.utils.translation import gettext_lazy as _
from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.contrib.auth.models import PermissionsMixin
from django.db import models
from django.utils import timezone


from django.conf import settings


class UserManager(BaseUserManager):
    """User manager"""

    def create_user(self, email, password=None, **extra_fields):
        """
        Creates and saves a User with the given email, date of
        birth and password.
        """
        if not email:
            raise ValueError("Users must have an email address")

        user = self.model(
            email=self.normalize_email(email),
        )

        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None):
        """
        Creates and saves a superuser with the given email, date of
        birth and password.
        """
        user = self.create_user(
            email=email,
            password=password,
        )
        user.is_admin = True
        user.is_active = True
        user.save(using=self._db)
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Abstract user model."""

    def upload_to(instance, filename):
        return 'images/user_{0}/{1}'.format(instance.id, filename)

    email = models.EmailField(
        verbose_name=_("email address"),
        max_length=255,
        unique=True,
    )
    username = None
    first_name = models.CharField(max_length=30, blank=True, verbose_name="first name")
    last_name = models.CharField(max_length=30, blank=True, verbose_name="last name")
    is_active = models.BooleanField(default=True, verbose_name="active")
    is_admin = models.BooleanField(default=False, verbose_name="admin")
    avatar = models.ImageField(upload_to=upload_to, null=True, blank=True)
    telegram = models.CharField(max_length=80, blank=True, null=True, verbose_name="Telegram")
    whatsapp = models.CharField(max_length=80, blank=True, null=True, verbose_name="WhatsApp")

    middle_name = models.CharField(max_length=30, blank=True, null=True, verbose_name="Отчество")
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    address = models.CharField(max_length=255, null=True, blank=True)
    gender = models.CharField(max_length=10, null=True, choices=[("male", "Мужской"), ("female", "Женский")], blank=True)
    birth_date = models.DateField(null=True, blank=True, verbose_name="День варенья")
    creation_date = models.DateTimeField(
        default=timezone.now, verbose_name=_("Creation date")
    )

    objects = UserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    def __str__(self):
        """return email"""
        return self.email

    def has_perm(self, perm, obj=None):
        """Does the user have a specific permission?
        Returns True if the user has the specified permission, where perm is in the format
         "<app label>.<permission codename>"
        (see permissions). If User.is_active and is_superuser are both True,
         this method always returns True."""
        # Simplest possible answer: Yes, always
        return True

    def has_module_perms(self, app_label):
        """Does the user have permissions to view the app `app_label`?"""
        # Simplest possible answer: Yes, always
        return True

    @property
    def is_staff(self):
        """Is the user a member of staff?.
        Returns True if the user has any permissions in the given package (the Django app label).
        If User.is_active and is_superuser are both True, this method always returns True."""
        # Simplest possible answer: All admins are staff
        return self.is_admin


class Profile(models.Model):
    """Дополнительная информация о пользователе"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='profile',
        null=True,       # теперь можно создавать профиль без пользователя
        blank=True       # удобно для форм/админки
    )
    email = models.EmailField(max_length=255)
    telegram = models.CharField(max_length=80, blank=True, null=True)
    whatsapp = models.CharField(max_length=80, blank=True, null=True)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    password = models.CharField(max_length=255)  # позже будешь шифровать
    city = models.CharField(max_length=100, null=True, blank=True)
    region = models.CharField(max_length=100, blank=True, null=True, verbose_name="Область")  # ✅ новое поле

    creation_date = models.DateTimeField(
        default=timezone.now, verbose_name=_("Creation date")
    )



    def __str__(self):
        if self.user:
            return f"Profile of {self.user.email}"
        elif self.email:
            return f"Profile of {self.email} (anonymous)"
        else:
            return f"Anonymous Profile #{self.id}"