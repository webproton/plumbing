from django.contrib import admin
from .models import SiteSettings



# Register your models here.
@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    list_display = ("phone", "email", "telegram", "whatsapp", "updated_at")