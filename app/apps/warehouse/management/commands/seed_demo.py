"""Демо-данные для ручной проверки: остатки на складе и (если каталог пуст) несколько товаров.

Остатки добавляются обычным приходом от «Демо-постачальника» через warehouse.stock — журнал и
кэши остатков сходятся. Движения журнала не удаляются, поэтому на боевой базе команду не запускать.
"""

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F, Q

from app.apps.accounts.models import User
from app.apps.products.models import Category, Product, ProductVariant
from app.apps.sellers.models import Seller
from app.apps.warehouse import stock
from app.apps.warehouse.models import Supplier, Warehouse

DEMO_SUPPLIER_CODE = "demo"
DEMO_DOCUMENT = "DEMO"
COST_RATIO = Decimal("0.7")

# категория → [(товар, [(код, вариант, цена)])]
DEMO_CATALOG = {
    "Змішувачі": [
        ("Змішувач для кухні з високим виливом", [("DEMO-01", "хром", 3450), ("DEMO-02", "чорний матовий", 3990)]),
        ("Змішувач для ванни з душовим набором", [("DEMO-03", None, 4200)]),
    ],
    "Унітази та інсталяції": [
        ("Унітаз-компакт з сидінням soft-close", [("DEMO-04", None, 5600)]),
        ("Інсталяція для підвісного унітазу з кнопкою", [("DEMO-05", None, 9800)]),
    ],
    "Труби та фітинги": [
        ("Труба PPR 20 мм PN20, 4 м", [("DEMO-06", None, 95)]),
        ("Кутик PPR 20 мм 90°", [("DEMO-07", None, 12)]),
        ("Кран кульовий", [("DEMO-08", '1/2" ВВ', 210), ("DEMO-09", '3/4" ВВ', 290)]),
    ],
    "Водонагрівачі": [
        ("Водонагрівач електричний 80 л", [("DEMO-10", None, 7900)]),
    ],
}


class Command(BaseCommand):
    help = "Демо-данные: приход остатков по товарам без остатка; пустой каталог — заполнить демо-товарами"

    def add_arguments(self, parser):
        parser.add_argument("--qty", type=int, default=20, help="сколько единиц приходовать на вариант (20)")
        parser.add_argument("--limit", type=int, default=100, help="максимум вариантов, 0 — все (100)")
        parser.add_argument("--seller", help="email продавца; по умолчанию — первый одобренный")
        parser.add_argument("--catalog", action="store_true", help="добавить демо-товары, даже если каталог не пуст")
        parser.add_argument("--force", action="store_true", help="разрешить при DEBUG=False (только тестовая база!)")

    def handle(self, *args, qty, limit, seller, catalog, force, **options):
        if not settings.DEBUG and not force:
            raise CommandError(
                "DEBUG=False: похоже на боевую базу. Приходы попадут в журнал склада и не удаляются. "
                "Если база тестовая — запустите с --force."
            )
        if qty <= 0:
            raise CommandError("--qty должен быть больше 0")

        with transaction.atomic():
            shop = self._seller(seller)
            warehouse = self._warehouse(shop)
            supplier, _created = Supplier.objects.get_or_create(
                code=DEMO_SUPPLIER_CODE, defaults={"name": "Демо-постачальник"}
            )
            need_catalog = catalog or not ProductVariant.objects.filter(available=True).exists()
            created = self._catalog(shop) if need_catalog else 0
            stocked = self._stock(shop, warehouse, supplier, qty, limit)

        self.stdout.write(f"Продавец: {shop.shop_name}; склад: {warehouse.name}")
        self.stdout.write(f"Новых демо-вариантов: {created}")
        self.stdout.write(self.style.SUCCESS(f"Оприходовано вариантов: {stocked} × {qty} шт."))

    def _seller(self, email):
        if email:
            shop = Seller.objects.filter(user__email__iexact=email).first()
            if shop is None:
                raise CommandError(f"Продавец {email} не найден")
            return shop
        shop = Seller.objects.filter(is_approved=True).order_by("id").first()
        if shop:
            return shop
        admin = User.objects.filter(is_superuser=True).order_by("id").first()
        if admin is None:
            raise CommandError("Нет ни продавца, ни суперпользователя — сначала createsuperuser")
        shop, _created = Seller.objects.get_or_create(
            user=admin, defaults={"shop_name": getattr(settings, "SITE_NAME", "") or "Демо-магазин"}
        )
        if not shop.is_approved:
            shop.is_approved = True
            shop.save(update_fields=["is_approved"])
        return shop

    def _warehouse(self, shop):
        warehouse = shop.warehouses.filter(is_default=True).first() or shop.warehouses.order_by("id").first()
        return warehouse or Warehouse.objects.create(seller=shop, name="Основний склад", is_default=True)

    def _catalog(self, shop):
        created = 0
        for category_name, products in DEMO_CATALOG.items():
            category, _new = Category.objects.get_or_create(name=category_name)
            for product_name, variants in products:
                product, _new = Product.objects.get_or_create(
                    name=product_name, seller=shop, defaults={"category": category}
                )
                for code, variant_name, price in variants:
                    _variant, new = ProductVariant.objects.get_or_create(
                        code=code,
                        defaults={
                            "product": product,
                            # как в редакторе товаров: полное название (товар + вариант)
                            "variant_name": f"{product_name}, {variant_name}" if variant_name else product_name,
                            "price": price,
                            "cost_price": Decimal(price) * COST_RATIO,
                            "available": True,
                        },
                    )
                    created += new
        return created

    def _stock(self, shop, warehouse, supplier, qty, limit):
        variants = (
            ProductVariant.objects.filter(available=True, price__gt=0, stock__lte=F("reserved"))
            .filter(Q(product__seller=shop) | Q(product__seller__isnull=True))
            .order_by("-product_id", "id")
        )
        variants = list(variants[:limit] if limit else variants)
        for variant in variants:
            stock.receive(
                variant,
                warehouse,
                qty,
                supplier=supplier,
                price_per_unit=variant.cost_price or (variant.price * COST_RATIO),
                document_number=DEMO_DOCUMENT,
                comment="seed_demo: тестовий прихід",
            )
        return len(variants)
