import uuid

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from app.apps.accounts.tests.factories import UserFactory  # предполагаем, что есть фабрика пользователя
from app.apps.orders.models import Cart, CartItems, Order
from app.apps.products.tests.factories import (  # предполагаем, что есть фабрика пользователя
    ProductFactory,
    ProductVariantFactory,
)


class CartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    customer = factory.SubFactory(UserFactory)
    created_at = factory.LazyFunction(timezone.now)


def stock_up(variant, quantity=100):
    """Положить товар на склад (через складской сервис, как в реальной жизни)."""
    from app.apps.warehouse import stock
    from app.apps.warehouse.tests.factories import SupplierFactory, WarehouseFactory

    warehouse = WarehouseFactory(is_default=True)
    stock.receive(variant, warehouse, quantity, supplier=SupplierFactory())
    return warehouse


class CartItemsFactory(DjangoModelFactory):
    class Meta:
        model = CartItems
        skip_postgeneration_save = True

    cart = factory.SubFactory(CartFactory)
    product = factory.SubFactory(ProductFactory)
    variant = factory.LazyAttribute(lambda o: o.product.variants.first() or ProductVariantFactory(product=o.product))
    quantity = 1

    @factory.post_generation
    def stocked(obj, create, extracted, **kwargs):
        """По умолчанию товар есть на складе; CartItemsFactory(stocked=0) — без остатка."""
        if create and obj.variant_id and extracted != 0:
            stock_up(obj.variant, extracted or 100)


class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    customer = factory.SubFactory(UserFactory)
    cart = factory.SubFactory(CartFactory)
    creation_date = factory.LazyFunction(timezone.now)
    total_price = 0
    status_order = Order.STATUS.in_processing
    payment_status = Order.PAYMENT_STATUS.waiting_for_payment
    address = factory.Faker("address")
    phone_number = factory.Faker("bothify", text="###########")  # до 11 цифр
    customer_name = factory.Faker("name")
    email = factory.Faker("email")
    intent_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    department_number = "1"
    city = factory.Faker("state")  # ✅ добавлено новое поле
    telegram = factory.Faker("user_name")
    whatsapp = factory.Faker("phone_number")
