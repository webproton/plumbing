import uuid
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from model_utils import Choices

from app.apps.products.models import Product, ProductVariant

User = get_user_model()


class Cart(models.Model):
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="carts", verbose_name="customer", null=True
    )

    cart_uuid = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
    )
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Creation date")  # Новое поле

    def calculate_total_price(self):
        """Текущая стоимость корзины (по актуальным ценам). Цена заказа фиксируется в OrderItem."""
        return sum((item.total_price for item in self.cart_items.select_related("variant")), Decimal("0"))

    def __str__(self):
        return f"Cart {self.id}"


class CartItems(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="cart_items", verbose_name="cart")
    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="cart_items_product", verbose_name="items products"
    )
    quantity = models.PositiveIntegerField(verbose_name="quantity product")
    variant = models.ForeignKey(
        ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="cart_items"
    )  # 👈 добавь это

    @property
    def total_price(self):
        if self.variant and self.variant.price:
            return self.variant.price * self.quantity
        return Decimal("0")

    def clean(self):
        # Custom validation to ensure product and cart relationships are valid
        if not self.product:
            raise ValidationError("A valid product must be associated with the cart item.")
        if not self.cart:
            raise ValidationError("A valid cart must be associated with the cart item.")


class Order(models.Model):
    """
    Модель Order:

    1. Для чего тут поле intent_id?
       Используется для хранения идентификатора, связанного с процессом оплаты или внешним API.

    2. Описание:
       - Создает заказ от клиента для обработки продавцом услуг.
       - Содержит информацию о получателе: ФИО, email, номер телефона для связи (опционально: Viber, Telegram, WhatsApp).
       - Адрес доставки: "Укрпочта", "Новая почта" или "Самовывоз".

    3. Основные функции:
       - Фиксирует дату создания заказа.
       - После прохождения всех проверок создается корзина и заказ.
       - Уведомление о создании заказа отправляется на email и в мессенджеры клиента.

    4. Информация в уведомлении:
       - Кто создал заказ.
       - Список позиций.
       - Общая сумма заказа.
       - Статус заказа.
       - Статус оплаты: оплачено или ожидает оплаты.

    5. Дополнительно:
       - Указываются реквизиты для оплаты на расчетный счет ФОПа.
       - Номер заказа, который необходимо указать при оплате.
       - Идентификатор заказа формируется из ID заказа и даты его создания.

    6. История заказов:
       - Пользователю доступен список всех его заказов с информацией о каждом из них.
    """

    # Типы доставки
    DELIVERY_CHOICES = Choices(("new_post", "Новая Почта"), ("self_pickup", "Самовывоз"))
    STATUS = Choices(
        ("in_processing", "В обработке"),
        ("delivered", "Доставлен"),
        ("delivering", "Доставляется"),
        ("completed", "Завершен"),
        ("canceled", "Отмена"),
    )

    PAYMENT_STATUS = Choices(
        ("waiting_for_payment", "Ожидание оплаты"),
        ("paid_for", "Оплачено"),
        ("canceled", "Отменен"),
        ("returned", "Возврат"),
        ("returning", "Возврат средств"),
    )

    PAYMENT_CHOICES = [
        ("full", "Полная оплата"),
        ("partial", "50% предоплата"),
    ]

    customer = models.ForeignKey(
        User, on_delete=models.SET_NULL, verbose_name="customer", related_name="orders", null=True, blank=True
    )
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="orders", verbose_name="cart")
    creation_date = models.DateTimeField(default=timezone.now, verbose_name=_("Creation date"))
    total_price = models.DecimalField(
        verbose_name=_("Total price"), max_digits=10, decimal_places=2, blank=True, null=True
    )
    status_order = models.CharField(
        max_length=50, choices=STATUS, verbose_name=_("Status order"), default=STATUS.in_processing
    )
    payment_status = models.CharField(
        max_length=50,
        choices=PAYMENT_STATUS,
        verbose_name=_("Payment status"),
        default=PAYMENT_STATUS.waiting_for_payment,
    )
    address = models.CharField(max_length=200, verbose_name="address delivery")
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    customer_name = models.CharField(verbose_name="customer name", max_length=50)
    email = models.EmailField(verbose_name="email", blank=True, null=True)
    intent_id = models.CharField(max_length=255, unique=True, blank=True, null=True, verbose_name="intent id")
    comment = models.TextField(blank=True, null=True, verbose_name="User comment", max_length=500)
    # Атрибуты доставки, если выбрана "Новая Почта"
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Город")

    department_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер отделения")
    # Атрибуты для самовывоза
    telegram = models.CharField(max_length=80, blank=True, null=True, verbose_name="Telegram")
    whatsapp = models.CharField(max_length=80, blank=True, null=True, verbose_name="WhatsApp")

    payment_type = models.CharField(max_length=10, choices=PAYMENT_CHOICES, default="full", verbose_name="Тип оплаты")

    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="managed_orders", verbose_name="Менеджер", null=True, blank=True
    )

    # Состояние товара по заказу (меняется только через app.apps.orders.services)
    STOCK_STATE = Choices(
        ("none", "Не резервировался"),  # заказы до введения резервов
        ("reserved", "Зарезервирован"),
        ("written_off", "Списан со склада"),
        ("released", "Резерв снят"),
    )
    stock_state = models.CharField(
        max_length=20, choices=STOCK_STATE, default=STOCK_STATE.none, verbose_name="Состояние товара"
    )

    class Meta:
        ordering = ["-creation_date"]
        indexes = [
            models.Index(fields=["customer", "-creation_date"], name="order_customer_date_idx"),
            models.Index(fields=["status_order"], name="order_status_idx"),
        ]

    def clean(self):
        if self.payment_type not in dict(self.PAYMENT_CHOICES).keys():
            raise ValidationError({"payment_type": "Выбран неверный способ оплаты."})

    def __str__(self):
        return f"Заказ #{self.pk}"


class OrderItem(models.Model):
    """Позиция заказа: снимок товара и цены на момент оформления."""

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, related_name="+")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="order_items")
    name = models.CharField(max_length=512, verbose_name="Наименование")
    sku = models.CharField(max_length=50, blank=True, default="", verbose_name="Артикул")
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, verbose_name="Цена за единицу")
    quantity = models.DecimalField(max_digits=12, decimal_places=3, verbose_name="Количество")

    class Meta:
        verbose_name = "Позиция заказа"
        verbose_name_plural = "Позиции заказа"
        constraints = [
            models.CheckConstraint(check=models.Q(quantity__gt=0), name="orderitem_quantity_positive"),
        ]

    @property
    def line_total(self):
        return (self.unit_price * self.quantity).quantize(Decimal("0.01"))

    def __str__(self):
        return f"{self.name} × {self.quantity}"
