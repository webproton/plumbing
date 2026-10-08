import factory
from factory.django import DjangoModelFactory
from django.utils import timezone
import uuid
from app.apps.orders.models import Cart, CartItems, Order
from app.apps.accounts.tests.factories import UserFactory  # предполагаем, что есть фабрика пользователя
from app.apps.products.tests.factories import ProductVariantFactory, ProductFactory  # предполагаем, что есть фабрика пользователя


class CartFactory(DjangoModelFactory):
    class Meta:
        model = Cart

    customer = factory.SubFactory(UserFactory)
    created_at = factory.LazyFunction(timezone.now)

class CartItemsFactory(DjangoModelFactory):
    class Meta:
        model = CartItems

    cart = factory.SubFactory(CartFactory)
    product = factory.SubFactory(ProductFactory)
    variant = factory.LazyAttribute(lambda o: o.product.variants.first() or ProductVariantFactory(product=o.product))
    quantity = 1

class OrderFactory(DjangoModelFactory):
    class Meta:
        model = Order

    customer = factory.SubFactory(UserFactory)
    cart = factory.SubFactory(CartFactory)
    creation_date = factory.LazyFunction(timezone.now)
    total_price = factory.LazyAttribute(lambda o: o.cart.calculate_total_price() if o.cart else 0)
    status_order = Order.STATUS.in_processing
    payment_status = Order.PAYMENT_STATUS.waiting_for_payment
    address = factory.Faker('address')
    phone_number = factory.Faker("bothify", text="###########")  # до 11 цифр
    customer_name = factory.Faker('name')
    email = factory.Faker('email')
    intent_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    department_number = "1"
    city = factory.Faker('state')  # ✅ добавлено новое поле
    telegram = factory.Faker('user_name')
    whatsapp = factory.Faker('phone_number')
