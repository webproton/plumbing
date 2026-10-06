# app/apps/warehouse/models.py
from django.db import models
from django.utils import timezone
from app.apps.sellers.models import Seller
from app.apps.products.models import ProductVariant
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db.models import Sum, Q



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
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, related_name='warehouses')
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
    """Главный журнал прихода/расхода/возврата"""
    TYPE_CHOICES = [
        ('in', 'Приход (поставка)'),
        ('out', 'Расход (продажа)'),
        ('return_in', 'Возврат от клиента'),
        ('return_out', 'Возврат поставщику'),
        ('adjustment', 'Корректировка остатка'),
        ('transfer_out', 'Перемещение (Убытие)'), # 🔥 Разделили типы перемещения для точного учета
        ('transfer_in', 'Перемещение (Прибытие)'),
    ]
    
    inventory_document = models.ForeignKey(
        'InventoryDocument',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Связанный документ"),
        related_name="stock_movements"
    )
    
    exchange_rate = models.DecimalField(
        max_digits=10, 
        decimal_places=4, 
        default=1.00, 
        verbose_name="Курс валюты к UAH"
    )

    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='movements', verbose_name=_("Вариант товара"))
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, verbose_name=_("Продавец"))
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, verbose_name=_("Склад"))
    movement_type = models.CharField(max_length=20, choices=TYPE_CHOICES, verbose_name=_("Тип движения"))
    # quantity = models.IntegerField(verbose_name=_("Количество"))
    
    quantity = models.DecimalField(max_digits=10, decimal_places=3, verbose_name=_("Количество"))
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True, verbose_name=_("Цена за единицу"))
    document_number = models.CharField(max_length=50, blank=True, null=True, verbose_name="Номер накладной")
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, verbose_name=_("Поставщик"))
    comment = models.TextField(blank=True, verbose_name=_("Комментарий"))
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Дата создания"))
    created_by = models.ForeignKey('accounts.User', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        verbose_name = _("Движение по складу")
        verbose_name_plural = _("Движения по складу")
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_movement_type_display()} — {self.variant} ({self.quantity})"
    
    def clean(self):
        # Проверка обязательного наличия склада
        if not self.warehouse:
            raise ValidationError("Склад обязателен для любого движения товара")

        # 🔥 ИСПРАВЛЕНО: Логика проверки остатков (учитывает новые маркеры transfer_in / transfer_out)
        if self.movement_type in ['out', 'transfer_out', 'return_out']:
            if self.variant and self.warehouse:
                current_stock = self.variant.movements.filter(
                    warehouse=self.warehouse
                ).aggregate(
                    total_in=Sum('quantity', filter=Q(movement_type__in=['in', 'return_in', 'adjustment', 'transfer_in'])),
                    total_out=Sum('quantity', filter=Q(movement_type__in=['out', 'return_out', 'transfer_out']))
                )
                
                # Если это редактирование старой записи, не учитываем её вес в текущем расходе
                total_out_val = current_stock['total_out'] or 0
                if self.pk:
                    total_out_val -= self.quantity

                balance = (current_stock['total_in'] or 0) - total_out_val
                if self.quantity > balance:
                    raise ValidationError(f"На складе {self.warehouse.name} недостаточно товара. Доступно: {balance} шт., запрашивается: {self.quantity} шт.")

        # Проверка поставщика для прихода
        if self.movement_type in ['in', 'return_out'] and not self.supplier:
            raise ValidationError("Для операций прихода или возврата поставщику необходимо указать поставщика.")


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
    seller = models.ForeignKey(Seller, on_delete=models.CASCADE, verbose_name=_("Продавец"))
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