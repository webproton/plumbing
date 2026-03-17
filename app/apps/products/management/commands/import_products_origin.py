import re
from decimal import Decimal
from pathlib import Path
from PIL import Image
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
import logging
# from webcolors import rgb_to_name, hex_to_rgb, CSS3_NAMES_TO_HEX
from webcolors import rgb_to_name, hex_to_rgb

# Настройка логирования
logger = logging.getLogger(__name__)


# Импорт моделей
from app.apps.products.models import (
    Product, ProductVariant, Category, ProductPhoto,
    Mechanism, MattressBase, UpholsteryMaterial,
    Pattern, BodyMaterial, Filling, Form,
    BedType, Armrest, IncludedItem, ColorOption, ColorProduct,Brand,Manufacturer, MaterialProduct,TypeOfProduct
)

# Словарь цветов CSS3
CSS3_COLORS = {
    'aliceblue': '#F0F8FF',
    'antiquewhite': '#FAEBD7',
    'aqua': '#00FFFF',
    'aquamarine': '#7FFFD4',
    'azure': '#F0FFFF',
    'beige': '#F5F5DC',
    'bisque': '#FFE4C4',
    'black': '#000000',
    'blanchedalmond': '#FFEBCD',
    'blue': '#0000FF',
    'blueviolet': '#8A2BE2',
    'brown': '#A52A2A',
    'burlywood': '#DEB887',
    'cadetblue': '#5F9EA0',
    'chartreuse': '#7FFF00',
    'chocolate': '#D2691E',
    'coral': '#FF7F50',
    'cornflowerblue': '#6495ED',
    'cornsilk': '#FFF8DC',
    'crimson': '#DC143C',
    'cyan': '#00FFFF',
    'darkblue': '#00008B',
    'darkcyan': '#008B8B',
    'darkgoldenrod': '#B8860B',
    'darkgray': '#A9A9A9',
    'darkgreen': '#006400',
    'darkkhaki': '#BDB76B',
    'darkmagenta': '#8B008B',
    'darkolivegreen': '#556B2F',
    'darkorange': '#FF8C00',
    'darkorchid': '#9932CC',
    'darkred': '#8B0000',
    'darksalmon': '#E9967A',
    'darkseagreen': '#8FBC8F',
    'darkslateblue': '#483D8B',
    'darkslategray': '#2F4F4F',
    'darkturquoise': '#00CED1',
    'darkviolet': '#9400D3',
    'deeppink': '#FF1493',
    'deepskyblue': '#00BFFF',
    'dimgray': '#696969',
    'dodgerblue': '#1E90FF',
    'firebrick': '#B22222',
    'floralwhite': '#FFFAF0',
    'forestgreen': '#228B22',
    'fuchsia': '#FF00FF',
    'gainsboro': '#DCDCDC',
    'ghostwhite': '#F8F8FF',
    'gold': '#FFD700',
    'goldenrod': '#DAA520',
    'gray': '#808080',
    'green': '#008000',
    'greenyellow': '#ADFF2F',
    'honeydew': '#F0FFF0',
    'hotpink': '#FF69B4',
    'indianred': '#CD5C5C',
    'indigo': '#4B0082',
    'ivory': '#FFFFF0',
    'khaki': '#F0E68C',
    'lavender': '#E6E6FA',
    'lavenderblush': '#FFF0F5',
    'lawngreen': '#7CFC00',
    'lemonchiffon': '#FFFACD',
    'lightblue': '#ADD8E6',
    'lightcoral': '#F08080',
    'lightcyan': '#E0FFFF',
    'lightgoldenrodyellow': '#FAFAD2',
    'lightgray': '#D3D3D3',
    'lightgreen': '#90EE90',
    'lightpink': '#FFB6C1',
    'lightsalmon': '#FFA07A',
    'lightseagreen': '#20B2AA',
    'lightskyblue': '#87CEFA',
    'lightslategray': '#778899',
    'lightsteelblue': '#B0C4DE',
    'lightyellow': '#FFFFE0',
    'lime': '#00FF00',
    'limegreen': '#32CD32',
    'linen': '#FAF0E6',
    'magenta': '#FF00FF',
    'maroon': '#800000',
    'mediumaquamarine': '#66CDAA',
    'mediumblue': '#0000CD',
    'mediumorchid': '#BA55D3',
    'mediumpurple': '#9370DB',
    'mediumseagreen': '#3CB371',
    'mediumslateblue': '#7B68EE',
    'mediumspringgreen': '#00FA9A',
    'mediumturquoise': '#48D1CC',
    'mediumvioletred': '#C71585',
    'midnightblue': '#191970',
    'mintcream': '#F5FFFA',
    'mistyrose': '#FFE4E1',
    'moccasin': '#FFE4B5',
    'navajowhite': '#FFDEAD',
    'navy': '#000080',
    'oldlace': '#FDF5E6',
    'olive': '#808000',
    'olivedrab': '#6B8E23',
    'orange': '#FFA500',
    'orangered': '#FF4500',
    'orchid': '#DA70D6',
    'palegoldenrod': '#EEE8AA',
    'palegreen': '#98FB98',
    'paleturquoise': '#AFEEEE',
    'palevioletred': '#DB7093',
    'papayawhip': '#FFEFD5',
    'peachpuff': '#FFDAB9',
    'peru': '#CD853F',
    'pink': '#FFC0CB',
    'plum': '#DDA0DD',
    'powderblue': '#B0E0E6',
    'purple': '#800080',
    'red': '#FF0000',
    'rosybrown': '#BC8F8F',
    'royalblue': '#4169E1',
    'saddlebrown': '#8B4513',
    'salmon': '#FA8072',
    'sandybrown': '#F4A460',
    'seagreen': '#2E8B57',
    'seashell': '#FFF5EE',
    'sienna': '#A0522D',
    'silver': '#C0C0C0',
    'skyblue': '#87CEEB',
    'slateblue': '#6A5ACD',
    'slategray': '#708090',
    'snow': '#FFFAFA',
    'springgreen': '#00FF7F',
    'steelblue': '#4682B4',
    'tan': '#D2B48C',
    'teal': '#008080',
    'thistle': '#D8BFD8',
    'tomato': '#FF6347',
    'turquoise': '#40E0D0',
    'violet': '#EE82EE',
    'wheat': '#F5DEB3',
    'white': '#FFFFFF',
    'whitesmoke': '#F5F5F5',
    'yellow': '#FFFF00',
    'yellowgreen': '#9ACD32',
}

def get_dominant_color(image_path, resize=150, ignore_white=True):
    img = Image.open(image_path)
    img = img.convert("RGB")
    img.thumbnail((resize, resize))

    colors = img.getcolors(resize * resize)
    if not colors:
        return None

    filtered_colors = []
    for count, color in colors:
        r, g, b = color
        # фильтруем белый или почти белый фон
        if ignore_white and r > 240 and g > 240 and b > 240:
            continue
        filtered_colors.append((count, color))

    if not filtered_colors:
        return None

    # берём самый частый цвет
    dominant_color = max(filtered_colors, key=lambda t: t[0])[1]
    return dominant_color
  


def is_mostly_white(photo_path, threshold=0.8):  # Уменьшите порог с 0.9 до 0.8
    try:
        img = Image.open(photo_path)
        img = img.convert("RGB")
        pixels = list(img.getdata())
        white_pixels = sum(1 for r, g, b in pixels if r > 240 and g > 240 and b > 240)
        return (white_pixels / len(pixels)) > threshold
    except Exception as e:
        logger.error(f"Ошибка в is_mostly_white для {photo_path}: {str(e)}")
        return False  # Не пропускать, если ошибка
    
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




def rgb_to_color_name(rgb_tuple):
    try:
        # Пробуем точное совпадение с CSS3 цветами
        return rgb_to_name(rgb_tuple, spec='css3')
    except ValueError:
        # Ищем ближайший цвет по евклидову расстоянию
        min_colors = {}
        for name, hex_value in CSS3_COLORS.items():
            r_c, g_c, b_c = hex_to_rgb(hex_value)
            # Евклидово расстояние между цветами
            dist = (r_c - rgb_tuple[0]) ** 2 + (g_c - rgb_tuple[1]) ** 2 + (b_c - rgb_tuple[2]) ** 2
            min_colors[dist] = name
        return min_colors[min(min_colors.keys())]
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

    
}

# 🔹 M2M-поля (ManyToManyField)
M2M_FIELDS = {
    "Материал обивки": ("upholstery_materials", UpholsteryMaterial),
    "Выбор цвета": ("color_options", ColorOption),
    "В комплект входит": ("included_items", IncludedItem),
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

                    # 🔹 Цикл обработки characteristics
                    for key, value in characteristics.items():
                        if key in FK_FIELDS:
                            attr_name, model_cls = FK_FIELDS[key]
                            obj, _ = model_cls.objects.get_or_create(name=value.strip())
                            setattr(variant, attr_name, obj)
                            continue

                        if key in M2M_FIELDS:
                            attr_name, model_cls = M2M_FIELDS[key]
                            for item in split_items(value):
                                obj, _ = model_cls.objects.get_or_create(name=item.strip())
                                getattr(variant, attr_name).add(obj)
                            continue

                        # Boolean поля
                        if key in ["Изготовление нестандартных размеров", "Ниша для хранения"]:
                            setattr(variant, MAP_FIELDS[key], parse_bool(value))
                            continue

                        # Числовые поля
                        field = MAP_FIELDS.get(key)
                        if field:
                            if "dimensions" in field or "bed_" in field or "seat_" in field:
                                setattr(variant, field, parse_mm(value))
                            elif field == "sleeping_places":
                                try:
                                    setattr(variant, field, int(value))
                                except:
                                    pass
                            else:
                                setattr(variant, field, value)


                    variant.save()

                    # --- фото ---
                    photos = list(sorted(
                        folder.glob("*.[wW][eE][bB][pP]"),  # Находит .webp, .WEBP, .WebP и т.д.
                        key=lambda p: int(p.stem) if p.stem.isdigit() else float('inf')
                    ))
                    photo_names = [p.name for p in photos]
                    self.stdout.write(self.style.NOTICE(f"  Найдено {len(photos)} WebP файлов в {folder}: {', '.join(photo_names)}"))

                    first_photo = None
                    # Проверяем наличие '1.webp' или '1.WEBP' явно
                    one_webp = None
                    for ext in ['1.webp', '1.WEBP']:
                        candidate = folder / ext
                        if candidate.exists() and candidate.is_file():
                            one_webp = candidate
                            break
                    if one_webp:
                        if not is_mostly_white(one_webp):
                            first_photo = one_webp
                        else:
                            self.stdout.write(self.style.WARNING(f"  {one_webp.name} существует, но пропущено (слишком белое)"))
                    else:
                        self.stdout.write(self.style.WARNING(f"  1.webp/1.WEBP не найден в {folder}"))

                    # Если '1.webp'/'1.WEBP' не подходит, берём первое из списка
                    if not first_photo and photos:
                        for photo_file in photos:
                            if not is_mostly_white(photo_file):
                                first_photo = photo_file
                                break

                    if first_photo:
                        try:
                            with open(first_photo, "rb") as f:
                                if not product.photo:
                                    product.photo.save(first_photo.name, File(f), save=True)
                                    product.save()

                            with open(first_photo, "rb") as f:
                                if not variant.photo:
                                    variant.photo.save(first_photo.name, File(f), save=True)
                                    variant.save()

                            rgb = get_dominant_color(first_photo)
                            if rgb:
                                color_name = rgb_to_color_name(rgb)
                                color_obj, _ = ColorOption.objects.get_or_create(name=color_name)
                                variant.color_options.add(color_obj)

                            self.stdout.write(self.style.SUCCESS(f"  └─ Главное фото добавлено: {first_photo.name}"))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  Ошибка при добавлении главного фото {first_photo.name}: {str(e)}"))
                            logger.error(f"Ошибка при добавлении главного фото {first_photo.name}: {str(e)}")
                    else:
                        self.stdout.write(self.style.WARNING(f"  Нет подходящего главного фото в {folder} (все белые или отсутствуют)"))

                    # --- дополнительные фото ---
                    for photo_file in photos:
                        if photo_file == first_photo:
                            self.stdout.write(self.style.NOTICE(f"  Пропущено (главное фото): {photo_file.name}"))
                            continue

                        self.stdout.write(self.style.NOTICE(f"  Проверяем фото: {photo_file.name}"))
                        try:
                            if is_mostly_white(photo_file):
                                self.stdout.write(self.style.WARNING(f"  Пропущено (слишком белое): {photo_file.name}"))
                                continue

                            rgb = get_dominant_color(photo_file)
                            if rgb:
                                color_name = rgb_to_color_name(rgb)
                                color_obj, _ = ColorOption.objects.get_or_create(name=color_name)
                                variant.color_options.add(color_obj)

                            with open(photo_file, "rb") as f:
                                ProductPhoto.objects.create(
                                    product=product,
                                    product_var=variant,
                                    photo=File(f, name=photo_file.name)
                                )
                            self.stdout.write(self.style.SUCCESS(f"  └─ Фото добавлено: {photo_file.name}"))
                        except Exception as e:
                            self.stdout.write(self.style.ERROR(f"  Ошибка при добавлении {photo_file.name}: {str(e)}"))
                            logger.error(f"Ошибка при добавлении фото {photo_file.name}: {str(e)}")





                    created_count += 1



                    # for photo_file in sorted(folder.glob("*.webp")):
                    #     # пропускаем схемы / чертежи
                    #     if is_mostly_white(photo_file):
                    #         continue

                    #     # определяем основной цвет
                    #     rgb = get_dominant_color(photo_file)
                    #     if rgb:
                    #         color_name = rgb_to_color_name(rgb)
                    #         color_obj, _ = ColorOption.objects.get_or_create(name=color_name)
                    #         variant.color_options.add(color_obj)

                    #     # сохраняем фото
                    #     with open(photo_file, "rb") as f:
                    #         if variant.photo is None:
                    #             variant.photo.save(photo_file.name, File(f), save=True)
                    #         else:
                    #             ProductPhoto.objects.create(
                    #                 product=product,
                    #                 product_var=variant,
                    #                 photo=File(f, name=photo_file.name)
                    #             )
                    #     self.stdout.write(self.style.SUCCESS(f"  └─ Фото добавлено: {photo_file.name}"))
