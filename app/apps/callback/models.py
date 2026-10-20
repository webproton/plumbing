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

    # Реквизиты для счёта на оплату (ручная оплата)
    legal_name = models.CharField("Получатель платежа", max_length=255, blank=True, default="")
    tax_id = models.CharField("ЄДРПОУ / ІПН", max_length=20, blank=True, default="")
    iban = models.CharField("IBAN", max_length=34, blank=True, default="")
    bank_name = models.CharField("Банк", max_length=255, blank=True, default="")
    legal_address = models.CharField("Адрес", max_length=255, blank=True, default="")
    vat_payer = models.BooleanField("Плательщик НДС", default=False)
    invoice_note = models.TextField("Примечание в счёте", blank=True, default="")

    # Отправка Новой Почтой (город/отделение — Ref из справочника НП)
    np_sender_city_ref = models.CharField(max_length=36, blank=True, default="")
    np_sender_city_name = models.CharField(max_length=255, blank=True, default="")
    np_sender_warehouse_ref = models.CharField(max_length=36, blank=True, default="")
    np_sender_warehouse_name = models.CharField(max_length=255, blank=True, default="")
    np_sender_phone = models.CharField("Телефон отправителя", max_length=20, blank=True, default="")

    # Маркетинг: пиксели (ID проверяются строго — они вставляются в скрипт на странице), фиды, Telegram
    ga4_id = models.CharField("Google Analytics 4 (G-…)", max_length=20, blank=True, default="")
    gtm_id = models.CharField("Google Tag Manager (GTM-…)", max_length=20, blank=True, default="")
    meta_pixel_id = models.CharField("Meta Pixel", max_length=20, blank=True, default="")
    tiktok_pixel_id = models.CharField("TikTok Pixel", max_length=30, blank=True, default="")
    feeds_enabled = models.BooleanField("Фиды товаров включены", default=False)
    feeds_token = models.CharField(max_length=32, blank=True, default="")
    telegram_channel = models.CharField("Канал Telegram (@имя или -100…)", max_length=64, blank=True, default="")
    telegram_autopost = models.BooleanField("Публиковать новинки в канал", default=False)

    # Письма покупателю: заказ принят, отправлен (ТТН), в отделении, оплата получена, отменён
    notify_customers = models.BooleanField("Уведомлять покупателей по email", default=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Настройки сайта"
        verbose_name_plural = "Настройки сайта"

    def __str__(self):
        return f"Настройки ({self.phone})"

    @classmethod
    def current(cls):
        return cls.objects.order_by("id").first() or cls()

    @property
    def has_requisites(self) -> bool:
        return bool(self.legal_name and self.iban)
