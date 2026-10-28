from allauth.account.models import EmailAddress
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from .models import Profile, User


class UserCreateForm(BaseUserCreationForm):
    class Meta:
        model = User
        fields = ("email",)


class UserEditForm(UserChangeForm):
    class Meta:
        model = User
        fields = "__all__"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Пользователи: пароль — только через формы Django (хранится хэшем, а не текстом).
    Созданному в админке почта сразу подтверждена — иначе он не войдёт (ACCOUNT_EMAIL_VERIFICATION=mandatory)."""

    add_form = UserCreateForm
    form = UserEditForm
    list_display = ("id", "email", "first_name", "last_name", "is_active", "is_admin")
    list_filter = ("is_active", "is_admin", "is_superuser")
    search_fields = ("email", "first_name", "last_name", "phone_number")
    ordering = ("-id",)
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Профиль", {"fields": ("first_name", "last_name", "middle_name", "phone_number", "telegram", "whatsapp",
                                "city", "address")}),
        ("Доступ", {"fields": ("is_active", "is_admin", "is_superuser", "groups", "user_permissions")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "password1", "password2")}),)
    filter_horizontal = ("groups", "user_permissions")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            EmailAddress.objects.update_or_create(
                user=obj, email=obj.email, defaults={"verified": True, "primary": True}
            )


class ProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "email", "phone_number", "city"]


admin.site.register(Profile, ProfileAdmin)
