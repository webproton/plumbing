"""
Импорт каталога.

ImportSource  — поставщик-источник товаров (фид по ссылке/файлу, JSON API, сайт с логином).
SupplierItem  — товар в каталоге поставщика (промежуточная таблица): обновляется при каждой
                синхронизации, связывается с нашим вариантом или публикуется как новый товар.
ImportRun     — один запуск: загрузка шаблона товаров или синхронизация источника (журнал + предпросмотр).
"""

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from app.apps.products.models import Category, ProductVariant
from app.apps.sellers.models import Seller
from app.apps.warehouse.models import Supplier
from app.core import crypto
from app.core.storage import private_storage


class ImportSource(models.Model):
    KIND_FEED, KIND_API, KIND_WEB = "feed", "api", "web"
    KINDS = [
        (KIND_FEED, _("Файл / фид (YML, XML, CSV, Excel)")),
        (KIND_API, _("JSON API")),
        (KIND_WEB, _("Сайт поставщика с логином")),
    ]
    FORMATS = [
        ("auto", _("Определить автоматически")),
        ("yml", "YML (Prom.ua, Rozetka)"),
        ("xml", "XML"),
        ("csv", "CSV"),
        ("xlsx", "Excel"),
        ("json", "JSON"),
    ]
    AUTH_NONE, AUTH_BASIC, AUTH_BEARER, AUTH_HEADER, AUTH_QUERY, AUTH_LOGIN = (
        "none",
        "basic",
        "bearer",
        "header",
        "query",
        "login",
    )
    AUTH_TYPES = [
        (AUTH_NONE, _("Без авторизации")),
        (AUTH_BASIC, _("Логин и пароль (HTTP Basic)")),
        (AUTH_BEARER, _("Токен (Bearer)")),
        (AUTH_HEADER, _("Ключ в заголовке")),
        (AUTH_QUERY, _("Ключ в параметре ссылки")),
        (AUTH_LOGIN, _("Вход на сайт (логин и пароль)")),
    ]
    PRICE_RRP, PRICE_MARKUP = "rrp", "markup"
    PRICE_MODES = [
        (PRICE_RRP, _("Рекомендованная цена поставщика")),
        (PRICE_MARKUP, _("Закупочная цена + наценка")),
    ]

    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="import_sources")
    supplier = models.ForeignKey(
        Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name="import_sources"
    )
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=10, choices=KINDS, default=KIND_FEED)
    url = models.URLField(max_length=1000, blank=True)
    file = models.FileField(upload_to="imports/sources/", storage=private_storage, blank=True)
    format = models.CharField(max_length=10, choices=FORMATS, default="auto")

    auth_type = models.CharField(max_length=10, choices=AUTH_TYPES, default=AUTH_NONE)
    # логин / имя заголовка / имя параметра
    auth_login = models.CharField(max_length=255, blank=True)
    # пароль / токен / значение ключа — только в зашифрованном виде (см. secret)
    secret_encrypted = models.TextField(blank=True)
    adapter = models.CharField(max_length=50, blank=True, help_text="Адаптер сайта поставщика (для kind=web)")

    # наше поле → колонка / тег / путь в JSON у поставщика: {"sku": "Артикул", "price": "prices.retail"}
    field_map = models.JSONField(default=dict, blank=True)
    # items_path, delimiter, encoding, sheet, page_param, max_pages…
    options = models.JSONField(default=dict, blank=True)

    currency = models.CharField(max_length=3, default="UAH", help_text="Валюта цен поставщика, если её нет в фиде")
    price_mode = models.CharField(max_length=10, choices=PRICE_MODES, default=PRICE_RRP)
    markup_percent = models.DecimalField(max_digits=6, decimal_places=2, default=30)
    price_rounding = models.DecimalField(
        max_digits=8, decimal_places=2, default=1, help_text="Округлять цену до (1 — до гривны, 0.01 — до копеек)"
    )
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, help_text="Категория для новых товаров"
    )
    publish_new = models.BooleanField(default=False, help_text="Новые товары сразу показывать на сайте")
    update_prices = models.BooleanField(default=True)
    hide_when_unavailable = models.BooleanField(
        default=False, help_text="Скрывать товар, если у поставщика его нет, а на нашем складе пусто"
    )
    sync_interval_minutes = models.PositiveIntegerField(default=0, help_text="0 — только вручную")
    is_active = models.BooleanField(default=True)

    last_sync_at = models.DateTimeField(null=True, blank=True)
    next_sync_at = models.DateTimeField(null=True, blank=True, db_index=True)
    last_status = models.CharField(max_length=10, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Источник товаров")
        verbose_name_plural = _("Источники товаров")
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def secret(self) -> str:
        return crypto.decrypt(self.secret_encrypted)

    @secret.setter
    def secret(self, value: str):
        self.secret_encrypted = crypto.encrypt(value or "")


class SupplierItem(models.Model):
    NEW, LINKED, IGNORED = "new", "linked", "ignored"
    STATUSES = [(NEW, _("Не связан")), (LINKED, _("Связан")), (IGNORED, _("Пропущен"))]

    source = models.ForeignKey(ImportSource, on_delete=models.CASCADE, related_name="items")
    external_id = models.CharField(max_length=255)
    sku = models.CharField(max_length=100, blank=True)
    barcode = models.CharField(max_length=50, blank=True)
    name = models.CharField(max_length=500, blank=True)
    brand = models.CharField(max_length=255, blank=True)
    category_name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    url = models.URLField(max_length=1000, blank=True)
    price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)  # рекомендованная
    old_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    cost = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)  # закупочная
    currency = models.CharField(max_length=3, blank=True)
    quantity = models.DecimalField(max_digits=12, decimal_places=3, null=True, blank=True)  # остаток у поставщика
    available = models.BooleanField(null=True)
    photos = models.JSONField(default=list, blank=True)
    params = models.JSONField(default=dict, blank=True)
    data_hash = models.CharField(max_length=64, blank=True)

    status = models.CharField(max_length=10, choices=STATUSES, default=NEW, db_index=True)
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="supplier_items"
    )
    match_method = models.CharField(max_length=10, blank=True)  # barcode / sku / auto / manual / created
    missing = models.BooleanField(default=False, help_text="Не пришёл в последней синхронизации")
    hidden_by_sync = models.BooleanField(default=False)
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(default=timezone.now)
    changed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _("Товар поставщика")
        verbose_name_plural = _("Товары поставщиков")
        constraints = [models.UniqueConstraint(fields=["source", "external_id"], name="supplier_item_unique_external")]
        indexes = [
            models.Index(fields=["source", "status"]),
            models.Index(fields=["barcode"]),
            models.Index(fields=["sku"]),
        ]
        ordering = ["name"]

    def __str__(self):
        return f"{self.source}: {self.name or self.external_id}"


class ImportRun(models.Model):
    KIND_TEMPLATE, KIND_SYNC = "template", "sync"
    KINDS = [(KIND_TEMPLATE, _("Шаблон товаров")), (KIND_SYNC, _("Синхронизация поставщика"))]
    PENDING, RUNNING, PREVIEW, APPLYING, DONE, FAILED = "pending", "running", "preview", "applying", "done", "failed"
    STATUSES = [
        (PENDING, _("В очереди")),
        (RUNNING, _("Выполняется")),
        (PREVIEW, _("Ожидает подтверждения")),
        (APPLYING, _("Применяется")),
        (DONE, _("Готово")),
        (FAILED, _("Ошибка")),
    ]
    ACTIVE = (PENDING, RUNNING, APPLYING)

    kind = models.CharField(max_length=10, choices=KINDS)
    status = models.CharField(max_length=10, choices=STATUSES, default=PENDING, db_index=True)
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name="import_runs")
    source = models.ForeignKey(ImportSource, on_delete=models.CASCADE, null=True, blank=True, related_name="runs")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    file = models.FileField(upload_to="imports/runs/", storage=private_storage, blank=True)
    file_name = models.CharField(max_length=255, blank=True)
    # параметры применения шаблона: склад для остатков, публиковать новые и т.п.
    options = models.JSONField(default=dict, blank=True)
    stats = models.JSONField(default=dict, blank=True)
    # строки предпросмотра шаблона: [{row, action, data, errors, warnings, variant_id}]
    rows = models.JSONField(default=list, blank=True)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = _("Запуск импорта")
        verbose_name_plural = _("Запуски импорта")
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_kind_display()} #{self.pk}"
