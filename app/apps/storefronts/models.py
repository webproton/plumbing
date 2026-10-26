"""
Витрина — «свой магазин» клиента на общей установке: только его направления (велосипеды, инструмент…)
и/или только его товары (продавцы), его название, цвет и контакты.

Как покупатель попадает на витрину (app.apps.storefronts.resolve):
  - свой домен клиента (velo-dnipro.com.ua) — поле domains;
  - ссылка ?store=<slug> (сервер по IP, демо для показа клиенту) — сайт запоминает выбор;
  - без витрины — общий магазин со всеми направлениями.
"""

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _

from app.apps.products.models import Category
from app.apps.sellers.models import Seller

VERTICAL_KEYS = [key for key, _label in Category.VERTICALS]


class Storefront(models.Model):
    slug = models.SlugField(
        max_length=50, unique=True, help_text="Адрес витрины: /?store=<slug> (например velo, instrument)"
    )
    name = models.CharField(max_length=120, verbose_name="Название магазина", help_text="Показывается в шапке сайта")
    tagline = models.CharField(max_length=255, blank=True, verbose_name="Подзаголовок (укр.)")
    tagline_ru = models.CharField(max_length=255, blank=True, verbose_name="Подзаголовок (рус.)")
    domains = models.TextField(
        blank=True, verbose_name="Домены", help_text="По одному на строку, без https:// и www: velo-dnipro.com.ua"
    )
    verticals = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Направления",
        help_text=f"Список из {', '.join(VERTICAL_KEYS)}. Пусто — все направления",
    )
    sellers = models.ManyToManyField(
        Seller,
        blank=True,
        related_name="storefronts",
        verbose_name="Продавцы",
        help_text="Пусто — товары всех продавцов",
    )
    brand_color = models.CharField(
        max_length=7,
        blank=True,
        validators=[RegexValidator(r"^#[0-9a-fA-F]{6}$", "Цвет в формате #1d6fa5")],
        verbose_name="Фирменный цвет",
    )
    logo = models.ImageField(upload_to="storefronts/", blank=True, null=True, verbose_name="Логотип")
    phone = models.CharField(max_length=30, blank=True, verbose_name="Телефон")
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True, verbose_name="Адрес")
    telegram_bot = models.CharField(max_length=64, blank=True, verbose_name="Telegram-бот магазина (@имя)")
    is_demo = models.BooleanField(default=False, verbose_name="Демо", help_text="Показывать в списке демо-витрин /demo")
    is_active = models.BooleanField(default=True, verbose_name="Активна")
    sort_order = models.PositiveIntegerField(default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Витрина")
        verbose_name_plural = _("Витрины")
        ordering = ["sort_order", "name"]

    def __str__(self):
        return self.name

    def clean(self):
        unknown = [v for v in self.verticals or [] if v not in VERTICAL_KEYS]
        if unknown:
            raise ValidationError({"verticals": f"Неизвестные направления: {', '.join(unknown)}"})

    @property
    def domain_list(self) -> list[str]:
        return [normalize_host(line) for line in self.domains.splitlines() if line.strip()]


def normalize_host(host: str) -> str:
    host = host.strip().lower().removeprefix("https://").removeprefix("http://").split("/")[0].split(":")[0]
    return host.removeprefix("www.")
