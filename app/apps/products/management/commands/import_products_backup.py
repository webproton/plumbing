import re
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

# Импорт моделей
from app.apps.products.models import (
    Product, ProductVariant, Category, ProductPhoto,
    Mechanism, MattressBase, UpholsteryMaterial,
    Pattern, BodyMaterial, Filling, Form,
    BedType, Armrest, IncludedItem, ColorOption, ColorProduct
)

  


# 🔹 утилиты для парсинга
def parse_mm(value):
    """Из '1940 мм', '1.3 m', '1320' -> Decimal"""
    if not value:
        return None
    v = str(value)
    m = re.search(r'(\d+(?:[\.,]\d+)?)', v)
    if not m:
        return None
    num = m.group(1).replace(',', '.')
    try:
        return Decimal(num)
    except Exception:
        return None


def parse_bool(value):
    if not value:
        return False
    low = value.lower()
    if "есть" in low or "да" in low:
        return True
    if "под заказ" in low:
        return True
    return False


def split_items(value):
    if not value:
        return []
    parts = re.split(r',|;|/|\band\b| и |\n', value)
    return [p.strip() for p in parts if p and p.strip()]

# 🔹 маппинг характеристик → поля модели
MAP_FIELDS = {
    "Тип товара":"bed_type",
    "Форма": "form",
    "Узор":"pattern",
    "Ширина": "dimensions_width",
    "Высота": "dimensions_height",
    "Глубина длинна": "dimensions_depth",
    "Механизм раскладки":"mechanism",
    "Ширина спального места": "bed_width",
    "Длина спального места": "bed_length",
    "Наполнение:":"filling",
    "Основание под матрас":"mattress_base",
    "Высота сидения": "seat_height",
    "Глубина сиденья": "seat_depth",
    "Подлокотники":"armrests",
    "Материал обивки":"upholstery_materials",
    "Выбор цвета":"color_options",
    "Цвет обивки":"color",
    "Материал корпуса":"body_material",
    "Спальных мест": "sleeping_places",
    "Изготовление нестандартных размеров": "custom_size_available",
    "Ниша для хранения": "storage_niche",
    "Особенность": "features",
    "В комплект входит":"included_items",
}


class Command(BaseCommand):
    help = "Импортирует продукты из каталогов divany и krovat (берёт description.txt + фото)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--limit",
            type=int,
            default=5,
            help="Сколько продуктов импортировать (по умолчанию 5)",
        )

    def handle(self, *args, **options):
        max_products = options["limit"]
        created_count = 0

        roots = [
            ("divany", Path(settings.BASE_DIR) / "divany" / "images"),
            ("krovat", Path(settings.BASE_DIR) / "krovat" / "images"),
        ]

        category_map = {
            "divany": "Диваны",
            "krovat": "Кровати",
        }

        for root_key, root_path in roots:
            if not root_path.exists():
                self.stdout.write(self.style.WARNING(f"Папка не найдена: {root_path}, пропускаю"))
                continue

            category, _ = Category.objects.get_or_create(name=category_map[root_key])
            self.stdout.write(self.style.SUCCESS(f"Категория: {category.name}"))

            for folder in sorted([p for p in root_path.iterdir() if p.is_dir()]):
                if created_count >= max_products:
                    self.stdout.write(self.style.WARNING(f"⏹ Лимит {max_products} достигнут"))
                    return

                with transaction.atomic():
                    product_name = folder.name.replace("_", " ")

                    product, created = Product.objects.get_or_create(
                        name=product_name, category=category
                    )
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"➕ Продукт: {product_name}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"⚠ Уже существует: {product_name}"))

                    # --- читаем description.txt ---
                    candidate = folder / "description.txt"
                    if not candidate.exists():
                        self.stdout.write(self.style.WARNING(f"  Нет description.txt в {folder}"))
                        continue

                    raw_text = candidate.read_text(encoding="utf-8", errors="ignore")
                    characteristics = {}
                    char_mode = False
                    for line in raw_text.splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        if line.startswith("Characteristics"):
                            char_mode = True
                            continue
                        if char_mode and ":" in line:
                            key, value = line.split(":", 1)
                            characteristics[key.strip()] = value.strip()

                    # --- создаём вариант ---
                    variant = ProductVariant.objects.create(
                        product=product,
                        variant_name=product_name,
                    )
                    self.stdout.write(self.style.SUCCESS(f"  └─ Вариант: {variant.variant_name}"))

                    # --- заполняем поля из characteristics ---
                    for key, value in characteristics.items():
                        if key in MAP_FIELDS:
                            field = MAP_FIELDS[key]
                            if field in ["custom_size_available", "storage_niche"]:
                                setattr(variant, field, parse_bool(value))
                            elif "dimensions" in field or "bed_" in field or "seat_" in field:
                                setattr(variant, field, parse_mm(value))
                            elif field == "sleeping_places":
                                try:
                                    setattr(variant, field, int(value))
                                except Exception:
                                    pass
                            else:
                                setattr(variant, field, value)

                        elif key == "Материал обивки":
                            for mat in split_items(value):
                                m, _ = UpholsteryMaterial.objects.get_or_create(name=mat)
                                variant.upholstery_materials.add(m)

                        elif key == "Материал корпуса":
                            for mat in split_items(value):
                                bm, _ = BodyMaterial.objects.get_or_create(name=mat)
                                variant.body_material = bm
                                
                        elif key == "Цвет обивки":
                            color, _ = ColorProduct.objects.get_or_create(name=value.strip())
                            variant.color = color

                        elif key == "Подлокотники":
                            armrest, _ = Armrest.objects.get_or_create(name=value.strip())
                            variant.armrests = armrest
                        elif key == "Наполнение":
                            f, _ = Filling.objects.get_or_create(name=value.strip())
                            variant.filling = f

                        elif key == "Основание под матрас":
                            mb, _ = MattressBase.objects.get_or_create(name=value.strip())
                            variant.mattress_base = mb

                        elif key == "Форма":
                            form, _ = Form.objects.get_or_create(name=value.strip())
                            variant.form = form

                        elif key == "Тип кровати":
                            bt, _ = BedType.objects.get_or_create(name=value.strip())
                            variant.bed_type = bt

                        elif key == "Узор":
                            p, _ = Pattern.objects.get_or_create(name=value.strip())
                            variant.pattern = p

                        elif key == "Механизм раскладки":
                            mech, _ = Mechanism.objects.get_or_create(name=value.strip())
                            variant.mechanism = mech

                        elif key == "Выбор цвета":
                            for c in split_items(value):
                                cobj, _ = ColorOption.objects.get_or_create(name=c)
                                variant.color_options.add(cobj)

                        elif key == "В комплект входит":
                            for it in split_items(value):
                                iobj, _ = IncludedItem.objects.get_or_create(name=it)
                                variant.included_items.add(iobj)

                    variant.save()

                    # --- фото ---
                    for img in sorted(folder.glob("*.webp")):
                        if img.name == "1.webp":
                            with open(img, "rb") as f:
                                product.photo.save(f"{product.id}_main.webp", File(f), save=True)
                            with open(img, "rb") as f:
                                variant.photo.save(f"{variant.id}_main.webp", File(f), save=True)
                            self.stdout.write(self.style.SUCCESS("  └─ Главное фото установлено"))
                        else:
                            with open(img, "rb") as f:
                                ProductPhoto.objects.create(
                                    product=product, product_var=variant,
                                    photo=File(f, name=img.name)
                                )
                            self.stdout.write(self.style.SUCCESS(f"  └─ Фото добавлено: {img.name}"))


                    created_count += 1
