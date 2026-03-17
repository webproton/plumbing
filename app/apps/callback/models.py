from django.db import models

# Create your models here.
class SiteSettings(models.Model):
    """_summary_

    Args:
        models (_type_): change info phone email etc for users

    Returns:
        _type_: _description_
    """
    phone = models.CharField(max_length=50, verbose_name="Телефон")
    email = models.EmailField(verbose_name="Email", blank=True, null=True)
    telegram = models.URLField(verbose_name="Telegram", blank=True, null=True)
    whatsapp = models.URLField(verbose_name="WhatsApp", blank=True, null=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return f"Настройки ({self.phone})"