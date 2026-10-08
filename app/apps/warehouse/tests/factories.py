import factory
from factory.django import DjangoModelFactory

from app.apps.accounts.tests.factories import UserFactory
from app.apps.sellers.models import Seller
from app.apps.warehouse.models import Supplier, Warehouse


class SellerFactory(DjangoModelFactory):
    class Meta:
        model = Seller

    user = factory.SubFactory(UserFactory)
    shop_name = factory.Sequence(lambda n: f"Shop {n}")
    is_approved = True


class WarehouseFactory(DjangoModelFactory):
    class Meta:
        model = Warehouse

    seller = factory.SubFactory(SellerFactory)
    name = factory.Sequence(lambda n: f"Склад {n}")
    is_default = False


class SupplierFactory(DjangoModelFactory):
    class Meta:
        model = Supplier

    name = factory.Sequence(lambda n: f"Поставщик {n}")
