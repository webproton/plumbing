from django.db import models
from django.utils.translation import gettext_lazy as _

from app.apps.products.models import Product


class TelegramPost(models.Model):
    """Товар, опубликованный в канал Telegram (чтобы не публиковать повторно автоматически)."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="telegram_posts")
    channel = models.CharField(max_length=64)
    message_id = models.BigIntegerField(null=True, blank=True)
    posted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Публикация в Telegram")
        verbose_name_plural = _("Публикации в Telegram")
        ordering = ["-posted_at"]
