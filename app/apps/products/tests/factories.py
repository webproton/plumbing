# apps/products/tests/factories.py
import factory
from factory.django import DjangoModelFactory

from app.apps.products.models import (
    Ball,
    Brand,
    Category,
    ColorProduct,
    MaterialProduct,
    Product,
    ProductVariant,
)


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    description = "Test category description"


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.Sequence(lambda n: f"Product {n}")
    category = factory.SubFactory(CategoryFactory)
    description = "Test product description"


class BrandFactory(DjangoModelFactory):
    class Meta:
        model = Brand

    name = factory.Sequence(lambda n: f"Brand {n}")


class MaterialProductFactory(DjangoModelFactory):
    class Meta:
        model = MaterialProduct

    name = factory.Sequence(lambda n: f"Material {n}")


class BallFactory(DjangoModelFactory):
    class Meta:
        model = Ball

    ball_material_type = factory.SubFactory(MaterialProductFactory)


class ColorProductFactory(DjangoModelFactory):
    class Meta:
        model = ColorProduct

    name = factory.Sequence(lambda n: f"Color {n}")


class ProductVariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariant

    product = factory.SubFactory(ProductFactory)
    price = 100
    available = True
    ball = factory.SubFactory(BallFactory)
    brand = factory.SubFactory(BrandFactory)
    material = factory.SubFactory(MaterialProductFactory)
    color = factory.SubFactory(ColorProductFactory)
