from django.contrib import admin

from .models import Profile, User


class UserAdmin(admin.ModelAdmin):
    """add user field  to admin dashboard"""

    list_display = ("id", "email", "first_name", "last_name")


class ProfileAdmin(admin.ModelAdmin):
    list_display = ["id", "user", "email", "password"]


admin.site.register(User, UserAdmin)

admin.site.register(Profile, ProfileAdmin)
