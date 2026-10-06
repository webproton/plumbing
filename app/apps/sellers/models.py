from django.db import models
from django.utils.text import slugify
from app.apps.accounts.models import User  # твой CustomUser
from django.utils.translation import gettext_lazy as _

class Seller(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='seller_profile')
    shop_name = models.CharField(max_length=255, unique=True, verbose_name="Название магазина")
    slug = models.SlugField(max_length=255, unique=True, blank=True)
    is_approved = models.BooleanField(default=False, verbose_name="Одобрен администратором")
    commission_percent = models.DecimalField(max_digits=5, decimal_places=2, default=15.00)
    verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    # реквизиты
    edrpou = models.CharField(max_length=20, blank=True, null=True, verbose_name="ЄДРПОУ")
    bank_account = models.CharField(max_length=50, blank=True, null=True)
    @property
    def is_active(self):
        """Активность продавца: пользователь и магазин должны быть активны"""
        shop_active = getattr(self, 'shop', None)
        if shop_active:
            return self.user.is_active and self.shop.active
        return self.user.is_active
    class Meta:
        verbose_name = _("Продавец")
        verbose_name_plural = _("Продавцы")
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
            if not self.slug:
                self.slug = slugify(self.shop_name)
                # предотвращаем коллизии
                original = self.slug
                counter = 1
                while Seller.objects.filter(slug=self.slug).exclude(pk=self.pk).exists():
                    self.slug = f"{original}-{counter}"
                    counter += 1
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.shop_name} ({self.user.email})"



class Shop(models.Model):
    seller = models.OneToOneField(Seller, on_delete=models.CASCADE, related_name='shop')
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='shops/logos/', blank=True)
    banner = models.ImageField(upload_to='shops/banners/', blank=True)
    active = models.BooleanField(default=True)
    address = models.CharField(max_length=255, blank=True)
    
    class Meta:
        verbose_name = _("Магазин")
        verbose_name_plural = _("Магазины")

    def __str__(self):
        return self.seller.shop_name