# app/apps/warehouse/models.py
from django.db import models
from app.apps.sellers.models import Seller
from app.apps.products.models import ProductVariant
from django.utils.translation import gettext_lazy as _
from django.db.models import Q


class CurrencyRate(models.Model):
    code = models.CharField(max_length=3, unique=True, help_text="USD, EUR и т.д.")
    rate = models.DecimalField(max_digits=10, decimal_places=2, help_text="Курс к гривне")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"1 {self.code} = {self.rate} UAH"


class Supplier(models.Model):
    """Поставщики товаров"""
    name = models.CharField(max_length=255, verbose_name="Название поставщика")
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Поставщик")
        verbose_name_plural = _("Поставщики")
        ordering = ['name']

    def __str__(self):
        return self.name


class Warehouse(models.Model):
    """Склады"""
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, related_name='warehouses')
    name = models.CharField(max_length=100, verbose_name="Название склада")
    address = models.CharField(max_length=255, blank=True)
    is_default = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Склад")
        verbose_name_plural = _("Склады")
        unique_together = ('seller', 'name')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.seller.shop_name})"


class StockMovement(models.Model):
    """
    Журнал движений товара — единственный источник истины об остатках.
    Записи не редактируются и не удаляются: ошибки исправляются встречным движением.
    Создавать движения нужно только через app.apps.warehouse.stock (он же обновляет кэши остатков).
    """
    IN = "in"
    OUT = "out"
    RETURN_IN = "return_in"
    RETURN_OUT = "return_out"
    ADJUSTMENT = "adjustment"
    ADJUSTMENT_OUT = "adjustment_out"
    TRANSFER_OUT = "transfer_out"
    TRANSFER_IN = "transfer_in"

    TYPE_CHOICES = [
        (IN, "Приход (поставка)"),
        (OUT, "Расход (продажа)"),
        (RETURN_IN, "Возврат от клиента"),
        (RETURN_OUT, "Возврат поставщику"),
        (ADJUSTMENT, "Инвентаризация: излишек"),
        (ADJUSTMENT_OUT, "Инвентаризация: недостача"),
        (TRANSFER_OUT, "Перемещение (убытие)"),
        (TRANSFER_IN, "Перемещение (прибытие)"),
    ]
    INCOMING_TYPES = (IN, RETURN_IN, ADJUSTMENT, TRANSFER_IN)
    OUTGOING_TYPES = (OUT, RETURN_OUT, ADJUSTMENT_OUT, TRANSFER_OUT)

    inventory_document = models.ForeignKey(
        'InventoryDocument',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        verbose_name=_("Связанный документ"),
        related_name="stock_movements"
    )

    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        default=1,
        verbose_name="Курс валюты к UAH"
    )

    variant = models.ForeignKey(
        ProductVariant, on_delete=models.PROTECT, related_name='movements', verbose_name=_("Вариант товара")
    )
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, verbose_name=_("Продавец"))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, verbose_name=_("Склад"))
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Тип движения"))
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name=_("Количество"))
    price_per_unit = models.DecimalField(
        max_digits=12, decimal_places=4, null=True, blank=True, verbose_name=_("Цена за единицу")
    )
    document_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Номер накладной")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Поставщик"))
    comment = models.TextField(blank=True, verbose_name=_("Комментарий"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Дата создания"))
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        verbose_name = _("Движение по складу")
        verbose_name_plural = _("Движения по складу")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=["variant", "warehouse", "movement_type"], name="stockmove_var_wh_type_idx"),
            models.Index(fields=["-created_at"], name="stockmove_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(check=Q(quantity__gt=0), name="stockmove_quantity_positive"),
        ]

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.variant} ({self.quantity})"

    @property
    def signed_quantity(self):
        return self.quantity if self.movement_type in self.INCOMING_TYPES else -self.quantity


class StockBalance(models.Model):
    """
    Текущий остаток варианта на конкретном складе (кэш журнала StockMovement).
    Строка блокируется select_for_update при каждой складской операции —
    это и защищает от гонок при одновременных списаниях.
    """
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="balances")
    warehouse = models.ForeignKey(Warehouse, on_delete=models.PROTECT, related_name="balances")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Остаток на складе")
        verbose_name_plural = _("Остатки на складах")
        constraints = [
            models.UniqueConstraint(fields=["variant", "warehouse"], name="stockbalance_variant_warehouse_uniq"),
        ]

    def __str__(self):
        return f"{self.variant} @ {self.warehouse}: {self.quantity}"


class InventoryDocument(models.Model):
    """Фото/файл накладной + OCR"""
    DOCUMENT_TYPE = [
        ('incoming', 'Приходная накладная'),
        ('outgoing', 'Расходная накладная'),
        ('return', 'Возврат'),
        ('other', 'Другое'),
    ]

    document_number = models.CharField(max_length=100, blank=True, null=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True)
    seller = models.ForeignKey(Seller, on_delete=models.PROTECT, verbose_name=_("Продавец"))
    document_type = models.CharField(max_length=20, choices=DOCUMENT_TYPE, verbose_name=_("Тип документа"))
    file = models.FileField(upload_to='invoices/%Y/%m/%d/', verbose_name="Фото/скан накладной")
    uploaded_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Загружено"))
    extracted_data = models.JSONField(blank=True, null=True, verbose_name="Данные после OCR")
    processed = models.BooleanField(default=False, verbose_name="Обработано OCR")

    class Meta:
        verbose_name = _("Накладная / документ")
        verbose_name_plural = _("Накладные / документы")
        ordering = ['-uploaded_at']

    def __str__(self):
        return f"{self.get_document_type_display()} — {self.seller} — {self.uploaded_at.date()}"


class ProductBarcode(models.Model):
    """Дополнительные штрихкоды вариантов (для сканера)"""
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="barcodes",
        verbose_name="Вариант штрихкода"
    )
    # 🔥 ИСПРАВЛЕНО: добавлен db_index=True для мгновенного поиска сканером
    code = models.CharField(max_length=128, unique=True, db_index=True, verbose_name="QR/Штрих")

    def __str__(self):
        return self.code


class VariantMatchMemory(models.Model):
    """Обучение системы сопоставления номенклатуры поставщиков с базой"""
    supplier = models.ForeignKey("warehouse.Supplier", on_delete=models.CASCADE, null=True, blank=True)
    # 🔥 ИСПРАВЛЕНО: Добавлены db_index для ускорения работы ИИ/OCR сопоставления
    raw_code = models.CharField(max_length=255, blank=True, null=True, db_index=True)
    raw_name = models.CharField(max_length=512, db_index=True)

    variant = models.ForeignKey("products.ProductVariant", on_delete=models.CASCADE)
    confidence = models.FloatField(default=1.0)
    hit_count = models.IntegerField(default=1)
    last_used = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("supplier", "raw_code", "raw_name", "variant")
