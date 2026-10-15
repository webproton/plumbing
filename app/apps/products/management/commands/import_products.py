import colorsys
import logging
import re
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from app.apps.products.models import (
    AngleVariant,
    Armrest,
    BedType,
    BodyMaterial,
    Brand,
    Category,
    ColorOption,
    ColorProduct,
    ExtraOrthopedicFilling,
    Filling,
    Form,
    FurnitureSetItem,
    IncludedItem,
    InteriorStyle,
    Manufacturer,
    MaterialProduct,
    MattressBase,
    MattressHardness,
    Mechanism,
    Pattern,
    Product,
    ProductPhoto,
    ProductVariant,
    TypeOfProduct,
    UpholsteryMaterial,
)
from app.apps.products.utils.color_utils import (
    boolean_keys,
    get_dominant_color_improved,
    get_or_create_ci,
    is_mostly_white,
    parse_bool,
    parse_mm,
    rgb_to_color_name,
    split_items,
)

logger = logging.getLogger(__name__)


def rgb_to_basic_color(rgb):
    """
    Расширенный набор цветов с приоритетами.
    Один цвет не попадает в несколько категорий.
    """
    r, g, b = [x / 255 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h_deg = h * 360

    # 1. Очень темные — венге, мокко, кофе
    if v < 0.1:
        return "Венге"

    # 2. Слабо насыщенные — серые / черные / белые
    if s < 0.15:
        if v > 0.85:
            return "Белый"
        elif v < 0.2:
            return "Черный"
        else:
            return "Серый"

    # 3. Красный спектр
    if 0 <= h_deg < 15 or 345 <= h_deg <= 360:
        return "Бордовый" if v < 0.4 else "Красный"

    # 4. Оранжевый
    elif 15 <= h_deg < 40:
        return "Масала" if v < 0.5 else "Оранжевый"

    # 5. Желтый / Лайм / Салатовый
    elif 40 <= h_deg < 65:
        if g > r and g > b:
            return "Салатовый"
        elif h_deg > 55:
            return "Лайм"
        return "Желтый"

    # 6. Зеленый
    elif 65 <= h_deg < 170:
        return "Тёмно-зелёный" if v < 0.35 else "Зеленый"

    # 7. Бирюзовый / Мятный
    elif 170 <= h_deg < 200:
        return "Мятный" if h_deg >= 180 else "Бирюзовый"

    # 8. Синий / Индиго
    elif 200 <= h_deg < 260:
        if v < 0.35:
            return "Тёмно-синий"
        elif 220 <= h_deg < 240:
            return "Индиго"
        return "Синий"

    # 9. Фиолетовый / Лавандовый
    elif 260 <= h_deg < 290:
        if s < 0.5:
            return "Лавандовый"
        elif v < 0.35:
            return "Бордовый"
        return "Фиолетовый"

    # 10. Розовый / Пудровый / Фуксия
    elif 290 <= h_deg < 345:
        if s < 0.5:
            return "Пудровый"
        elif h_deg > 320:
            return "Фуксия"
        return "Розовый"

    return "Неопределенный"


def rgb_to_extended_color_quantized(rgb):
    name = rgb_to_basic_color(rgb)
    if not name:
        return None
    # объединяем близкие оттенки в один цвет
    mapping = {
        "Венге": "Бордовый",
        "Терракотовый": "Красный",
        "Масала": "Оранжевый",
        "Тёмно-зелёный": "Зеленый",
        "Тёмно-синий": "Синий",
        "Пудровый": "Розовый",
        "Бордовый": "Бордовый",
    }
    return mapping.get(name, name)


# Словарь цветов CSS3


FURNITURE_COLOR_MAP = {
    # Древесные оттенки
    "венге": "brown",
    "орех": "brown",
    "дуб": "brown",
    "бук": "brown",
    "ясень": "brown",
    "клен": "brown",
    "вишня": "brown",
    "шоколад": "brown",
    "кофе": "brown",
    "какао": "brown",
    "карамель": "brown",
    "капучино": "brown",
    "марон": "brown",
    "натуральное дерево": "brown",
    # Белые / светлые оттенки
    "белый": "white",
    "сливочный": "white",
    "айвори": "white",
    "перламутр": "white",
    "молочный": "white",
    "бежевый": "beige",
    "кремовый": "beige",
    "ваниль": "beige",
    "светлый дуб": "beige",
    # Серые / графит
    "серый": "gray",
    "антрацит": "gray",
    "графит": "gray",
    "серебро": "gray",
    "туман": "gray",
    "асфальт": "gray",
    "дымчатый": "gray",
    # Черные / темные
    "черный": "black",
    "глубокий черный": "black",
    "венге темный": "black",
    "чёрное дерево": "black",
    # Красные / бордо
    "красный": "red",
    "бордовый": "red",
    "вишневый": "red",
    "марсала": "red",
    "гранат": "red",
    # Синие / голубые
    "синий": "blue",
    "голубой": "blue",
    "морская волна": "blue",
    "бирюзовый": "blue",
    "лазурный": "blue",
    # Зеленые
    "зеленый": "green",
    "мята": "green",
    "оливковый": "green",
    "изумруд": "green",
    "фисташковый": "green",
    # Желтые / золотые
    "желтый": "yellow",
    "золотой": "yellow",
    "горчичный": "yellow",
    "лимонный": "yellow",
    "солнце": "yellow",
    # Оранжевые / терракот
    "оранжевый": "orange",
    "терракот": "orange",
    "коррал": "orange",
    "персиковый": "orange",
    # Фиолетовые / пурпурные
    "фиолетовый": "purple",
    "сиреневый": "purple",
    "лаванда": "purple",
    "лиловый": "purple",
    # Розовые
    "розовый": "pink",
    "пудровый": "pink",
    "пепельно-розовый": "pink",
    # Универсальные / нестандартные
    "шампань": "beige",
    "капучино светлый": "beige",
    "дуб молочный": "beige",
    "серо-бежевый": "gray",
    "антрацитовый": "gray",
    "черный матовый": "black",
    "белый глянец": "white",
}


# 🔹 утилиты для парсинга


# 🔹 маппинг характеристик → поля модели

# 🔹 маппинг характеристик → поля модели

MAP_FIELDS = {
    "Изготовление нестандартных размеров": "custom_size_available",
    "Ниша для хранения": "storage_niche",
    "Ширина": "dimensions_width",
    "Высота": "dimensions_height",
    "Глубина длинна": "dimensions_depth",
    "Спальных мест": "sleeping_places",
    "Ширина спального места": "bed_width",
    "Длина спального места": "bed_length",
    "Высота сидения": "seat_height",
    "Глубина сиденья": "seat_depth",
    # добавленные
    "Высота в разложенном виде": "expanded_height",
    "Высота изножья кровати": "footboard_height",
    "Высота подлокотника": "armrest_height",
    "Максимальная нагрузка": "max_load",
    "Срок изготовления": "production_time_days",
    "Толщина корпуса": "dimensions_thickness",
    "Толщина фасада": "facade_thickness",
    "Количество дверей": "doors_count",
    "Ширина на выбор": "width_options",
    "Ширина подлокотника": "armrest_width",
    "Ширина сиденья": "seat_width",
    "Ширина угла кухни": "corner_width",
    "Ширина кухни": "dimensions_width",
    "Ширина в разложенном виде": "expanded_width",  # <- поле еще нужно создать, если требуется
    # "Цвета на выбор": "color_options",      # для случаев, когда приходит CSV со списком цветов
    "Фасад с витриной": "facade_with_showcase",
    "Конструктор 3D": "has_3d_constructor",
    "Эффект Зима-Лето": "winter_summer_effect",
    "Ящики на направляющих": "drawers",
    "Чехол": "cover",
    "Цена": "price",
    "Ценовой сегмент": "price_segment",
    "Гарантия": "warranty",
    "Гарантийный срок": "warranty_period_months",
    "Пол": "gender",
    "Серия": "series",
    "Ниша для телевизора": "tv_niche",
    "Оформление фасада": "facade_design",
    "Верхние модули (текст)": "upper_modules",
    "Нижние модули (текст)": "lower_modules",
}

# 🔹 FK-поля (ForeignKey)
FK_FIELDS = {
    "Подлокотники": ("armrests", Armrest),
    "Цвет обивки": ("color", ColorProduct),
    "Наполнение": ("filling", Filling),
    "Основание под матрас": ("mattress_base", MattressBase),
    "Форма": ("bed_type_form", Form),
    "Тип кровати": ("bed_type", BedType),
    "Узор": ("pattern", Pattern),
    "Механизм раскладки": ("mechanism", Mechanism),
    "Тип товара": ("type_of_product", TypeOfProduct),
    "Материал": ("material", MaterialProduct),
    "Бренд": ("brand", Brand),
    "Производитель": ("manufacturer", Manufacturer),
    "Материал корпуса": ("body_material", BodyMaterial),
    # 🔹 Новые
    "Материал ножек": ("legs_material", MaterialProduct),
    "Интерьерный стиль": ("interior_style", InteriorStyle),
    "Столешница": ("countertop_material", MaterialProduct),
    "Цвет ножек": ("legs_color", ColorOption),
    "Цвет столешницы": ("countertop_color", ColorOption),
    "Цвет фасада": ("facade_color", ColorOption),
}

# 🔹 M2M-поля (ManyToManyField)
M2M_FIELDS = {
    "Материал обивки": ("upholstery_materials", UpholsteryMaterial),
    "Выбор цвета": ("color_options", ColorOption),
    "В комплект входит": ("included_items", IncludedItem),
    # 🔹 Новые
    "Цвета на выбор": ("color_options", ColorOption),  # для кухонь (список)
    "Жесткость матраса": ("mattress_hardnesses", MattressHardness),
    "Комплектация гарнитура": ("furniture_set", FurnitureSetItem),
    "Варианты угла": ("angle_variants", AngleVariant),
    "Дополнительное ортопедическое наполнение на выбор": ("extra_orthopedic_fillings", ExtraOrthopedicFilling),
}


# Значения, которые не считаем цветами
INVALID_COLOR_VALUES = [
    "подбор из наличия тканей на складе",
    "из фабричного каталога",
    "стандарт",
    "под заказ на ваш выбор",
    "цвет на выбор",
]


class Command(BaseCommand):
    help = "Импортирует продукты из каталогов divany и krovat (берёт description1.txt + фото)"

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
            ("detskaya-mebel", Path(settings.BASE_DIR) / "detskaya-mebel" / "images"),
            ("kitchen", Path(settings.BASE_DIR) / "kitchen" / "images"),
            ("komplect-mebeli", Path(settings.BASE_DIR) / "komplect-mebeli" / "images"),
            ("pufy", Path(settings.BASE_DIR) / "pufy" / "images"),
            ("shkafy", Path(settings.BASE_DIR) / "shkafy" / "images"),
            ("stolstyl", Path(settings.BASE_DIR) / "stolstyl" / "images"),
            ("vse-dlya-obustroystva-kukhni", Path(settings.BASE_DIR) / "vse-dlya-obustroystva-kukhni" / "images"),
            ("ofisnye-divany", Path(settings.BASE_DIR) / "ofisnye-divany" / "images"),
            ("matrasy-ortopedicheskie", Path(settings.BASE_DIR) / "matrasy-ortopedicheskie" / "images"),
            ("gostinye", Path(settings.BASE_DIR) / "gostinye" / "images"),
            ("prihozhie", Path(settings.BASE_DIR) / "prihozhie" / "images"),
            ("kresla", Path(settings.BASE_DIR) / "kresla" / "images"),
            ("komody-tumby", Path(settings.BASE_DIR) / "komody-tumby" / "images"),
        ]

        category_map = {
            "divany": "Диваны",
            "krovat": "Кровати",
            "detskaya-mebel": "Детская мебель",
            "kitchen": "Кухни",
            "komplect-mebeli": "Комплекты мебели",
            "pufy": "Пуфы",
            "shkafy": "Шкафы",
            "stolstyl": "Стол Стул",
            "vse-dlya-obustroystva-kukhni": "Все для кухни",
            "ofisnye-divany": "Офисные диваны",
            "matrasy-ortopedicheskie": "Матрасы",
            "gostinye": "Гостинные",
            "prihozhie": "Прихожие",
            "kresla": "Кресла",
            "komody-tumby": "Комоды-Тумбы",
        }

        for root_key, root_path in roots:
            if not root_path.exists():
                self.stdout.write(self.style.WARNING(f"Папка не найдена: {root_path}, пропускаю"))
                continue

            # slug = ключ категории
            category, created = Category.objects.get_or_create(
                name=category_map[root_key],
                defaults={"slug": root_key},  # здесь slug равен ключу
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f"Категория создана: {category.name} ({category.slug})"))
            else:
                # если категория уже есть, принудительно обновим slug на нужный
                if category.slug != root_key:
                    category.slug = root_key
                    category.save()
                    self.stdout.write(self.style.SUCCESS(f"Категория обновлена: {category.name} ({category.slug})"))
                else:
                    self.stdout.write(self.style.SUCCESS(f"Категория: {category.name} ({category.slug})"))

            for folder in sorted([p for p in root_path.iterdir() if p.is_dir()]):
                if created_count >= max_products:
                    self.stdout.write(self.style.WARNING(f"⏹ Лимит {max_products} достигнут"))
                    return

                with transaction.atomic():
                    product_name = folder.name.replace("_", " ")

                    product, created = Product.objects.get_or_create(name=product_name, category=category)
                    if created:
                        self.stdout.write(self.style.SUCCESS(f"➕ Продукт: {product_name}"))
                    else:
                        self.stdout.write(self.style.WARNING(f"⚠ Уже существует: {product_name}"))

                    # --- читаем description.txt ---
                    candidate = folder / "description1.txt"
                    if not candidate.exists():
                        self.stdout.write(self.style.WARNING(f"  Нет description1.txt в {folder}"))
                        continue

                    raw_text = candidate.read_text(encoding="utf-8", errors="ignore")
                    characteristics = {}
                    char_mode = False
                    short_desc_mode = False
                    short_desc_lines = []

                    for line in raw_text.splitlines():
                        line = line.strip()
                        if not line:
                            continue

                        if line.startswith("Short Description (from catalog)"):
                            short_desc_mode = True
                            char_mode = False
                            continue

                        # Конец блока Short Description, начало другого заголовка
                        if line.endswith("(from product page):") or line.startswith("Characteristics"):
                            short_desc_mode = False
                            if line.startswith("Characteristics"):
                                char_mode = True
                            continue

                        if line.startswith("Characteristics"):
                            char_mode = True
                            short_desc_mode = False
                            continue

                        # Собираем строки Short Description
                        if short_desc_mode:
                            short_desc_lines.append(line)
                            continue

                        if char_mode and ":" in line:
                            key, value = line.split(":", 1)
                            characteristics[key.strip()] = value.strip()
                    short_description = "\n".join(short_desc_lines).strip()

                    # --- собираем список уникальных цветов ---
                    # --- собираем список уникальных цветов ---
                    colors = set()  # уникальные цвета
                    photo_color_map = {}  # привязка цвета к списку фото
                    first_photo = None

                    # Извлекаем цвета из атрибутов
                    # if "Цвет обивки" in characteristics:
                    #     value = characteristics["Цвет обивки"].strip().lower()
                    #     if value not in invalid_values:
                    #         main_color = characteristics["Цвет обивки"].strip()
                    #         colors.add(main_color)

                    # if "Цвета на выбор" in characteristics:
                    #     attr_colors = split_items(characteristics["Цвета на выбор"])
                    #     attr_colors = [c for c in attr_colors if c.strip().lower() not in invalid_values]
                    #     colors.update(attr_colors)
                    # elif "Выбор цвета" in characteristics:
                    #     value = characteristics["Выбор цвета"].strip().lower()
                    #     if value not in invalid_values:
                    #         attr_colors = split_items(characteristics["Выбор цвета"])
                    #         attr_colors = [c for c in attr_colors if c.strip().lower() not in invalid_values]
                    #         colors.update(attr_colors)

                    self.stdout.write(
                        self.style.SUCCESS(f"  Цвета из атрибутов: {', '.join(colors) if colors else 'Нет'}")
                    )

                    # --- цвета ---
                    colors = set()
                    photo_color_map = {}
                    first_photo = None

                    # --- фото ---
                    photos = list(
                        sorted(
                            folder.glob("*.[wW][eE][bB][pP]"),  # Находит .webp, .WEBP, .WebP и т.д.
                            key=lambda p: int(p.stem) if p.stem.isdigit() else float("inf"),
                        )
                    )
                    photo_names = [p.name for p in photos]
                    self.stdout.write(
                        self.style.NOTICE(f"  Найдено {len(photos)} WebP файлов в {folder}: {', '.join(photo_names)}")
                    )

                    # определяем цвета по фото

                    for photo_file in photos:
                        if is_mostly_white(photo_file):
                            self.stdout.write(self.style.WARNING(f"  Пропущено (слишком белое): {photo_file.name}"))
                            continue

                        # rgb = get_dominant_color(photo_file)
                        rgb = get_dominant_color_improved(photo_file)
                        if not rgb:
                            continue

                        # css_color_name = rgb_to_color_name(rgb)
                        # base_color = normalize_to_basic_color(css_color_name)
                        base_color = rgb_to_basic_color(rgb)

                        # base_color = rgb_to_extended_color_quantized(rgb)

                        if not base_color:
                            continue  # пропускаем слишком темные/светлые/неопределенные цвета

                        # игнорируем "под заказ", "цвет на выбор" и т.п.
                        if base_color.lower() in INVALID_COLOR_VALUES:
                            continue

                        colors.add(base_color)
                        photo_color_map.setdefault(base_color, []).append(photo_file)

                        if not first_photo:
                            first_photo = photo_file

                    self.stdout.write(
                        self.style.SUCCESS(f"  Цвета из фото: {', '.join(sorted(colors)) if colors else 'Нет'}")
                    )

                    # --- создаём варианты продукта ---
                    variants = []
                    if colors:
                        self.stdout.write(
                            self.style.SUCCESS(f"  Создаём варианты по цветам: {', '.join(sorted(colors))}")
                        )
                        color_option_objs = {c: get_or_create_ci(ColorOption, c)[0] for c in colors}

                        for color_name in sorted(colors):
                            slug = f"{product.slug}-{color_name.lower().replace(' ', '-')}"
                            variant_name = f"{product_name} ({color_name})"
                            variant = ProductVariant.objects.create(
                                product=product,
                                variant_name=variant_name,
                                description=short_description or None,
                                slug=slug,
                            )
                            self.fill_variant_fields(variant, characteristics)

                            color_product, _ = get_or_create_ci(ColorProduct, color_name)
                            variant.color = color_product

                            variant.color_options.add(*color_option_objs.values())

                            # Привязываем фото к варианту
                            for photo_file in photo_color_map.get(color_name, []):
                                try:
                                    with open(photo_file, "rb") as f:
                                        if not variant.photo:
                                            variant.photo.save(photo_file.name, File(f), save=True)
                                except Exception as e:
                                    self.stdout.write(
                                        self.style.ERROR(
                                            f"  Ошибка при добавлении фото {photo_file.name} для варианта {variant_name}: {str(e)}"
                                        )
                                    )
                                    logger.error(f"Ошибка при добавлении фото {photo_file.name}: {str(e)}")

                            variant.save()
                            variants.append(variant)
                            self.stdout.write(
                                self.style.SUCCESS(f"    └─ Создан вариант: {variant_name} (slug: {slug})")
                            )
                    else:
                        # fallback: один вариант без цвета
                        variant_name = product_name
                        slug = product.slug or product_name.lower().replace(" ", "-")
                        variant = ProductVariant.objects.create(
                            product=product,
                            variant_name=variant_name,
                            description=short_description or None,
                            slug=slug,
                        )
                        self.fill_variant_fields(variant, characteristics)
                        if first_photo:
                            try:
                                with open(first_photo, "rb") as f:
                                    if not variant.photo:
                                        variant.photo.save(first_photo.name, File(f), save=True)
                            except Exception as e:
                                self.stdout.write(
                                    self.style.ERROR(f"  Ошибка при добавлении фото {first_photo.name}: {str(e)}")
                                )
                                logger.error(f"Ошибка при добавлении фото {first_photo.name}: {str(e)}")
                        variant.save()
                        variants.append(variant)
                        self.stdout.write(self.style.WARNING(f"  └─ Создан fallback-вариант без цвета: {variant_name}"))

                    # --- главное фото для продукта ---
                    # --- главное фото для продукта ---
                    # --- главное фото для продукта и первого варианта ---
                    if first_photo:
                        try:
                            with open(first_photo, "rb") as f:
                                if not product.photo:
                                    product.photo.save(first_photo.name, File(f), save=True)
                            if variants:
                                first_variant = variants[0]
                                with open(first_photo, "rb") as f:
                                    if not first_variant.photo:
                                        first_variant.photo.save(first_photo.name, File(f), save=True)
                        except Exception as e:
                            self.stdout.write(
                                self.style.ERROR(f"Ошибка при добавлении главного фото {first_photo.name}: {e}")
                            )
                            logger.error(f"Ошибка при добавлении главного фото {first_photo.name}: {e}")
                    else:
                        self.stdout.write(
                            self.style.WARNING(f"Нет подходящего главного фото в {folder} (все белые или отсутствуют)")
                        )

                    # --- дополнительные фото ---
                    # --- дополнительные фото ---
                    for photo_file in photos:
                        if photo_file == first_photo:
                            self.stdout.write(self.style.NOTICE(f"Пропущено (главное фото): {photo_file.name}"))
                            continue
                        if is_mostly_white(photo_file):
                            self.stdout.write(self.style.WARNING(f"Пропущено (слишком белое): {photo_file.name}"))
                            continue

                        try:
                            # rgb = get_dominant_color(photo_file)
                            rgb = get_dominant_color_improved(photo_file)
                            photo_color_name = None
                            if rgb:
                                rgb_to_color_name(rgb)
                                photo_color_name = rgb_to_basic_color(rgb)
                                if not photo_color_name:
                                    continue  # пропускаем слишком темные/светлые/неопределенные цвета

                                if photo_color_name.lower() in INVALID_COLOR_VALUES:
                                    photo_color_name = None

                            with open(photo_file, "rb") as f:
                                if photo_color_name:
                                    target_variant = next(
                                        (
                                            v
                                            for v in variants
                                            if f"{product_name} ({photo_color_name})" == v.variant_name
                                        ),
                                        None,
                                    )
                                    if target_variant:
                                        ProductPhoto.objects.create(
                                            product=product,
                                            product_var=target_variant,
                                            photo=File(f, name=photo_file.name),
                                        )
                                        self.stdout.write(
                                            self.style.SUCCESS(
                                                f"Фото добавлено к варианту {target_variant.variant_name}: {photo_file.name}"
                                            )
                                        )
                                    else:
                                        # Если нет варианта с таким цветом — добавляем ко всем
                                        for variant in variants:
                                            ProductPhoto.objects.create(
                                                product=product,
                                                product_var=variant,
                                                photo=File(f, name=photo_file.name),
                                            )
                                        self.stdout.write(
                                            self.style.SUCCESS(
                                                f"Фото добавлено ко всем вариантам (цвет не найден): {photo_file.name}"
                                            )
                                        )
                                else:
                                    # Цвет не определён или rgb == None → добавляем ко всем
                                    for variant in variants:
                                        ProductPhoto.objects.create(
                                            product=product, product_var=variant, photo=File(f, name=photo_file.name)
                                        )
                                    self.stdout.write(
                                        self.style.SUCCESS(
                                            f"Фото добавлено ко всем вариантам (цвет не определён): {photo_file.name}"
                                        )
                                    )

                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"Ошибка при добавлении {photo_file.name}: {str(e)}"))
                            logger.error(f"Ошибка при добавлении фото {photo_file.name}: {str(e)}")

                    # else:
                    #     self.stdout.write(self.style.WARNING(f"  Нет подходящего главного фото в {folder} (все белые или отсутствуют)"))

                    created_count += 1

    def fill_variant_fields(self, variant, characteristics):
        """Заполняет поля варианта по characteristics"""

        def _clean_numeric_for_decimal(s: str) -> str:
            """Очищает строку, оставляя цифры, точку, запятую и минус.
            Преобразует пробелы-разделители тысяч и запятую в точку.
            Примеры:
            '22 100 ₴.' -> '22100'
            '1 234,56 ₴' -> '1234.56'
            """
            if not s:
                return ""
            # Убираем всё кроме цифр, точек, запятых и минуса
            cleaned = re.sub(r"[^\d\.,\-]", "", s)
            # Если одновременно есть и запятая, и точка, предполагаем, что точка — разделитель тысяч -> удалить точки
            if "." in cleaned and "," in cleaned:
                cleaned = cleaned.replace(".", "")
                cleaned = cleaned.replace(",", ".")
            else:
                # заменим запятую на точку (десятичный разделитель)
                cleaned = cleaned.replace(",", ".")
                # удалим пробелы (тысячные)
                cleaned = cleaned.replace(" ", "")
            # ещё раз убрать пробелы и лишние символы
            cleaned = cleaned.strip()
            return cleaned

        def _to_decimal_or_none(s: str):
            """Пытается вернуть Decimal или None."""
            if s is None:
                return None
            cleaned = _clean_numeric_for_decimal(str(s))
            if cleaned == "":
                return None
            try:
                # Decimal принимает строки вида '22100' или '1234.56'
                return Decimal(cleaned)
            except InvalidOperation:
                return None

        def _extract_first_int_mm(s: str):
            """Вытаскивает первое целое число (мм) из строки вроде '1400; 1600; 1800 мм.' или '1400 мм'."""
            if not s:
                return None
            # Найдём первое вхождение числа (целого или десятичного)
            m = re.search(r"(\d+)", s.replace("\xa0", " "))
            if m:
                try:
                    return int(m.group(1))
                except Exception:
                    return None
            return None

        for key, value in characteristics.items():
            # 1) FK
            if key in FK_FIELDS:
                attr_name, model_cls = FK_FIELDS[key]
                if value:
                    obj, _ = get_or_create_ci(model_cls, value.strip())
                    if obj:
                        setattr(variant, attr_name, obj)
                continue

            # 2) Цвета (уже обработаны выше)
            if key in ("Выбор цвета", "Цвета на выбор"):
                low = (value or "").lower()
                customizable_tokens = ("под заказ", "на выбор", "на ваш выбор", "под заказ на ваш выбор")
                if any(tok in low for tok in customizable_tokens):
                    if hasattr(variant, "is_color_customizable"):
                        variant.is_color_customizable = True
                continue

            # 3) M2M
            if key in M2M_FIELDS:
                attr_name, model_cls = M2M_FIELDS[key]
                for item in split_items(value):
                    obj, _ = get_or_create_ci(model_cls, item)
                    if obj:
                        getattr(variant, attr_name).add(obj)
                continue

            # 4) Boolean
            if key in boolean_keys:
                mapped = MAP_FIELDS.get(key)
                try:
                    if mapped:
                        setattr(variant, mapped, parse_bool(value))
                    elif hasattr(variant, key):
                        setattr(variant, key, parse_bool(value))
                except Exception:
                    self.stdout.write(self.style.WARNING(f"  Не удалось распарсить boolean для {key}: {value}"))
                continue

            # 5) MAP_FIELDS (числовые и текстовые)
            field = MAP_FIELDS.get(key)
            if field:
                # если поле связано с размерами — вытаскиваем первое число (мм)
                if (
                    "dimensions" in field
                    or field.startswith(("bed_", "seat_"))
                    or field.endswith(("_width", "_height"))
                ):
                    mm = _extract_first_int_mm(value)
                    if mm is not None:
                        setattr(variant, field, mm)
                    else:
                        # пытаться парсить через существующий util, если есть (fallback)
                        try:
                            setattr(variant, field, parse_mm(value))
                        except Exception:
                            pass

                # для некоторых полей (возможно, гарантия/время/нагрузка) оставляем прежнюю логику
                elif field in ("warranty_period_months", "production_time_days", "max_load"):
                    try:
                        setattr(variant, field, float(re.sub(r"[^\d.,]", "", str(value)).replace(",", ".")))
                    except Exception:
                        pass

                elif field == "sleeping_places":
                    try:
                        setattr(variant, field, int(str(value).strip()))
                    except Exception:
                        pass

                else:
                    # Попробуем аккуратно распарсить как Decimal (цена/стоимость), если в value есть пробелы или валюта или запятая/точка
                    # Условие: если в строке есть пробелы внутри цифр или буквы валюты — попробуем Decimal
                    try_decimal = False
                    if isinstance(value, str):
                        # если есть пробел между цифрами OR есть буквенные символы (₴, руб, ₴.) OR есть запятая/точка в числе
                        if re.search(r"\d+\s+\d+", value) or re.search(r"[^\d\.,\s\-]", value):
                            try_decimal = True
                        if re.search(r"[,\.\d]+", value) and any(sym in value for sym in (",", ".")):
                            try_decimal = True

                    if try_decimal:
                        dec = _to_decimal_or_none(value)
                        if dec is not None:
                            # записываем Decimal в поле
                            try:
                                setattr(variant, field, dec)
                            except Exception:
                                # если поле не принимает Decimal, fallback — записываем как строку
                                try:
                                    setattr(variant, field, value)
                                except Exception:
                                    pass
                            continue

                    # по умолчанию — записываем как строку (или как есть)
                    try:
                        setattr(variant, field, value)
                    except Exception:
                        # если не удалось, просто игнорируем
                        pass
                continue

            # Логируем нераспознанное
            self.stdout.write(self.style.NOTICE(f"  Не распознан ключ: {key} (значение: {value})"))

        variant.save()
