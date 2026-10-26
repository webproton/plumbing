"""
Демо-витрины для показа клиентам: python app/manage.py seed_storefronts [--products [--force]]

Витрины: velo (велосипеды), instrument (инструмент), santekhnika (сантехника) — открываются по /?store=<slug>,
список — на странице /demo. Существующие витрины не перезаписываются.
--products — ещё и демо-товары велосипедов и инструмента (в их категориях дерева направлений). Они видны и в общем
магазине, поэтому на рабочей базе — только осознанно, с --force.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from app.apps.accounts.models import User
from app.apps.products.catalog.services import ensure_taxonomy
from app.apps.products.catalog.taxonomy import VERTICALS
from app.apps.products.models import Product, ProductVariant
from app.apps.sellers.models import Seller
from app.apps.storefronts.demo import DEMO_PRODUCTS, DEMO_STOREFRONTS
from app.apps.storefronts.models import Storefront
from app.apps.warehouse import stock
from app.apps.warehouse.models import Supplier, Warehouse

COST_RATIO = Decimal("0.7")
DEMO_QTY = 10  # остаток демо-товаров: на витрине они «в наличии»


class Command(BaseCommand):
    help = "Демо-витрины (велосипеды, инструмент, сантехника) и, по желанию, демо-товары"

    def add_arguments(self, parser):
        parser.add_argument("--products", action="store_true", help="добавить демо-товары велосипедов и инструмента")
        parser.add_argument("--force", action="store_true", help="разрешить демо-товары при DEBUG=False")

    def handle(self, *args, products=False, force=False, **options):
        created = 0
        for data in DEMO_STOREFRONTS:
            _storefront, new = Storefront.objects.get_or_create(
                slug=data["slug"], defaults={**{k: v for k, v in data.items() if k != "slug"}, "is_demo": True}
            )
            created += new
        self.stdout.write(f"Демо-витрин создано: {created} (всего {len(DEMO_STOREFRONTS)}); открыть: /demo")

        if not products:
            return
        if not settings.DEBUG and not force:
            raise CommandError("Демо-товары попадут и в общий магазин. На рабочей базе запустите с --force.")
        seller = self._seller()
        warehouse = Warehouse.objects.filter(seller=seller, is_default=True).first() or Warehouse.objects.create(
            seller=seller, name="Основний склад", is_default=True
        )
        supplier, _created = Supplier.objects.get_or_create(code="demo", defaults={"name": "Демо-постачальник"})
        added = 0
        for vertical_key, items in DEMO_PRODUCTS.items():
            categories = ensure_taxonomy(VERTICALS[vertical_key])
            for category_slug, name, variants in items:
                product, _new = Product.objects.get_or_create(
                    name=name, seller=seller, defaults={"category": categories[category_slug]}
                )
                for code, variant_name, price in variants:
                    variant, new = ProductVariant.objects.get_or_create(
                        code=code,
                        defaults={
                            "product": product,
                            "variant_name": f"{name}, {variant_name}" if variant_name else name,
                            "price": price,
                            "cost_price": Decimal(price) * COST_RATIO,
                            "available": True,
                        },
                    )
                    added += new
                    if new:
                        stock.receive(
                            variant,
                            warehouse,
                            DEMO_QTY,
                            supplier=supplier,
                            price_per_unit=variant.cost_price,
                            document_number="DEMO",
                            comment="seed_storefronts: демо-залишок",
                        )
        self.stdout.write(f"Демо-товаров (вариантов) добавлено: {added}")

    def _seller(self) -> Seller:
        seller = Seller.objects.filter(is_approved=True).order_by("id").first()
        if seller:
            return seller
        admin = User.objects.filter(is_superuser=True).order_by("id").first()
        if admin is None:
            raise CommandError("Нет ни продавца, ни суперпользователя — сначала createsuperuser")
        seller, _created = Seller.objects.get_or_create(user=admin, defaults={"shop_name": "Демо-магазин"})
        if not seller.is_approved:
            seller.is_approved = True
            seller.save(update_fields=["is_approved"])
        return seller
