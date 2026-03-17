import uuid
from django.db import models
from model_utils import Choices
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from app.apps.products.models import Product, ProductVariant
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

User = get_user_model()

class Cart(models.Model):
    
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="carts", verbose_name="customer", null=True)
    
    cart_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True,)
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Creation date")  # Новое поле

    def calculate_total_price(self):
        total = 0
        for item in self.cart_items.select_related('variant'):
            total += item.total_price  # Используем уже готовое свойство из CartItems
        return total


    def __str__(self):
        return f"Cart {self.id}"
      
      
class CartItems(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE,related_name="cart_items",verbose_name="cart")
    product = models.ForeignKey(Product, on_delete=models.CASCADE,related_name="cart_items_product",verbose_name="items products")
    quantity = models.PositiveIntegerField(verbose_name="quantity product")
    variant = models.ForeignKey(ProductVariant, on_delete=models.SET_NULL, null=True, blank=True, related_name="cart_items")  # 👈 добавь это

    
    @property
    def total_price(self):
        if self.variant and self.variant.price:
            return self.variant.price * self.quantity
        return 0
      
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
    DELIVERY_CHOICES = Choices(
        ("new_post", "Новая Почта"),
        ("self_pickup", "Самовывоз")
    )
    STATUS = Choices(
        ("in_processing","В обработке"), 
        ("delivered","Доставлен"),
        ("delivering","Доставляется"),
        ("completed","Завершен"), 
        ("canceled","Отмена"))


    PAYMENT_STATUS = Choices(
        ( "waiting_for_payment","Ожидание оплаты"),
        ("paid_for","Оплачено"),
        ("canceled","Отменен"),
        ( "returned","Возврат"), 
        ("returning","Возврат средств")
        )
    
    PAYMENT_CHOICES = [
        ('full', 'Полная оплата'),
        ('partial', '50% предоплата'),
    ]

    customer = models.ForeignKey(
        User, on_delete=models.SET_NULL, verbose_name="customer", related_name="orders", null=True,blank=True
    )
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name="orders", verbose_name="cart"
    )
    creation_date = models.DateTimeField(
        default=timezone.now, verbose_name=_("Creation date")
    )
    total_price = models.DecimalField(
        verbose_name=_("Total price"), max_digits=10, decimal_places=2, blank=True, null=True
    )
    status_order = models.CharField(
        max_length=50, choices=STATUS, verbose_name=_("Status order"), default=STATUS.in_processing
    )
    payment_status = models.CharField(
        max_length=50, choices=PAYMENT_STATUS, verbose_name=_("Payment status"), default=PAYMENT_STATUS.waiting_for_payment
    )
    address = models.CharField(max_length=200, verbose_name="address delivery")
    phone_number = models.CharField(max_length=15, blank=True, null=True)  
    customer_name = models.CharField(verbose_name="customer name", max_length=50)
    email = models.EmailField(verbose_name="email", blank=True, null=True)
    intent_id = models.CharField(
        max_length=255, unique=True, blank=True, null=True, verbose_name="intent id"
    )
    comment = models.TextField(blank=True, null=True, verbose_name="User comment" , max_length=500)
    # Атрибуты доставки, если выбрана "Новая Почта"
    city = models.CharField(max_length=100, blank=True, null=True, verbose_name="Город")
    # country = models.CharField(max_length=100, blank=True, null=True, verbose_name="Страна")

    # region = models.CharField(max_length=100, blank=True, null=True, verbose_name="Регион")  # ✅ новое поле
    department_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Номер отделения")
    # zip_code = models.PositiveIntegerField(blank=True,null=True, verbose_name="zip code")
    # Атрибуты для самовывоза
    telegram = models.CharField(max_length=80, blank=True, null=True, verbose_name="Telegram")
    whatsapp = models.CharField(max_length=80, blank=True, null=True, verbose_name="WhatsApp")

    payment_type = models.CharField(
        max_length=10,
        choices=PAYMENT_CHOICES,
        default='full',
        verbose_name="Тип оплаты"
    )


    manager = models.ForeignKey(
        User, on_delete=models.SET_NULL,
        related_name="managed_orders",
        verbose_name="Менеджер",
        null=True, blank=True
    )

    def clean(self):
        # Валидация типа оплаты
        if self.payment_type not in dict(self.PAYMENT_CHOICES).keys():
            raise ValidationError({"payment_type": "Выбран неверный способ оплаты."})

    def save(self, *args, **kwargs):
        # Если total_price пустое, вычисляем стоимость на основе корзины
        if self.total_price is None and self.cart:
            self.total_price = self.cart.calculate_total_price()
        super().save(*args, **kwargs)
  
