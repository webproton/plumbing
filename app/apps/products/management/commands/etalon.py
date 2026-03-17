import re
from decimal import Decimal, InvalidOperation
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
    BedType, Armrest, IncludedItem, ColorOption, ColorProduct,Brand,Manufacturer, MaterialProduct,TypeOfProduct,
    InteriorStyle,MattressHardness,FurnitureSetItem,AngleVariant,ExtraOrthopedicFilling
)



boolean_keys = {
    "Изготовление нестандартных размеров",
    "Ниша для хранения",
    "Фасад с витриной",
    "Конструктор 3D",
    "Ниша для телевизора",
    "Эффект Зима-Лето",
    # добавь сюда при необходимости ещё булевых ключей
}

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

BASIC_COLOR_MAP = {
    "white": ["white", "snow", "ghostwhite", "aliceblue", "mintcream", "ivory", "floralwhite"],
    "black": ["black", "gray", "dimgray", "slategray", "darkslategray"],
    "red": ["red", "darkred", "firebrick", "crimson", "indianred", "maroon"],
    "green": ["green", "darkgreen", "forestgreen", "seagreen", "limegreen", "mediumseagreen", "olive", "darkolivegreen", "yellowgreen"],
    "blue": ["blue", "navy", "midnightblue", "royalblue", "dodgerblue", "skyblue", "steelblue", "teal", "cyan"],
    "yellow": ["yellow", "gold", "khaki", "lightyellow", "lemonchiffon", "goldenrod"],
    "brown": ["brown", "saddlebrown", "chocolate", "peru", "tan", "burlywood", "beige", "wheat"],
    "purple": ["purple", "indigo", "darkmagenta", "orchid", "violet", "plum", "lavender", "mediumorchid"],
    "pink": ["pink", "lightpink", "deeppink", "hotpink", "fuchsia"],
    "orange": ["orange", "darkorange", "coral", "tomato", "orangered", "sandybrown"],
    "gray": ["lightgray", "silver", "gainsboro", "darkgray", "dimgray", "slategray"],
    "other": []  # fallback для всех остальных цветов
}

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

def is_too_dark(rgb, threshold=30):
    r, g, b = rgb
    return (r + g + b) / 3 < threshold

def is_valid_color(rgb_tuple, dark_thresh=40, light_thresh=230):
    r, g, b = rgb_tuple
    avg = (r + g + b) / 3

    # слишком тёмный (чёрный / шум)
    if avg < dark_thresh:
        return False

    # слишком светлый (белый / фон)
    if avg > light_thresh:
        return False

    return True



def normalize_to_basic_color(color_name: str) -> str:
    """Приводит CSS3-цвет к базовому (red, green, blue, и т.п.)"""
    color_name = color_name.lower().strip()
    for basic, synonyms in BASIC_COLOR_MAP.items():
        if color_name in synonyms or color_name == basic:
            return basic
    return color_name  # если не нашли — оставляем как есть

def get_dominant_color(image_path, resize=150, ignore_white=True, ignore_dark=True):
    """Возвращает доминантный цвет изображения (RGB), с фильтром белого и черного."""
    img = Image.open(image_path)
    img = img.convert("RGB")
    img.thumbnail((resize, resize))

    colors = img.getcolors(resize * resize)
    if not colors:
        return None

    filtered_colors = []
    for count, color in colors:
        r, g, b = color
        # фильтруем белый
        if ignore_white and r > 240 and g > 240 and b > 240:
            continue
        # фильтруем черный / слишком темный
        if ignore_dark and max(color) < 40:
            continue
        filtered_colors.append((count, color))

    if not filtered_colors:
        return None

    # берём самый частый оставшийся цвет
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


def get_or_create_ci(model_cls, name):
    """Ищет объект по name case-insensitive, иначе создаёт с оригинальным name."""
    name = (name or "").strip()
    if not name:
        return None, False
    obj = model_cls.objects.filter(name__iexact=name).first()
    if obj:
        return obj, False
    return model_cls.objects.get_or_create(name=name)

def rgb_to_color_name(rgb_tuple):
    try:
        # пробуем точное совпадение
        return rgb_to_name(rgb_tuple, spec='css3')
    except ValueError:
        # ищем ближайший базовый цвет
        min_dist = float('inf')
        closest_name = None
        for name, hex_val in CSS3_COLORS.items():
            r_c, g_c, b_c = hex_to_rgb(hex_val)
            dist = (r_c - rgb_tuple[0])**2 + (g_c - rgb_tuple[1])**2 + (b_c - rgb_tuple[2])**2
            if dist < min_dist:
                min_dist = dist
                closest_name = name
        return closest_name


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
    "Ширина в разложенном виде": "expanded_width",   # <- поле еще нужно создать, если требуется
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
    "Цвета на выбор": ("color_options", ColorOption), # для кухонь (список)
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
            ("komplectmebeli", Path(settings.BASE_DIR) / "komplectmebeli" / "images"),
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
            "detskayamebel": "Детская мебель",
            "kitchen": "Кухни",
            "komplectmebeli": "Комплекты мебели" ,
            "pufy":"Пуфы",
            "shkafy":"Шкафы",
            "stolstyl": "Стол Стул",
            "vse-dlya-obustroystva-kukhni": "Все для кухни",
            "ofisnyedivany":"Офисные диваны",
            "matrasyortopedicheskie":"Матрасы",
            "gostinye":"Гостинные",
            "prihozhie":"Прихожие",
            "kresla": "Кресла",
            "komodytumby":"Комоды-Тумбы"
        }


        for root_key, root_path in roots:
            if not root_path.exists():
                self.stdout.write(self.style.WARNING(f"Папка не найдена: {root_path}, пропускаю"))
                continue

            # slug = ключ категории
            category, created = Category.objects.get_or_create(
                name=category_map[root_key],
                defaults={"slug": root_key}  # здесь slug равен ключу
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

                    product, created = Product.objects.get_or_create(
                        name=product_name, category=category
                    )
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

                    invalid_values = [
                        "подбор из наличия тканей на складе",
                        "из фабричного каталога",
                        "стандарт",
                        "под заказ на ваш выбор",
                        "цвет на выбор",
                        "Цвет обивки"
                    ]

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

                    self.stdout.write(self.style.SUCCESS(f"  Цвета из атрибутов: {', '.join(colors) if colors else 'Нет'}"))

                    # --- цвета ---
                    colors = set()
                    photo_color_map = {}
                    first_photo = None

                    # --- фото ---
                    photos = list(sorted(
                        folder.glob("*.[wW][eE][bB][pP]"),  # Находит .webp, .WEBP, .WebP и т.д.
                        key=lambda p: int(p.stem) if p.stem.isdigit() else float('inf')
                    ))
                    photo_names = [p.name for p in photos]
                    self.stdout.write(self.style.NOTICE(f"  Найдено {len(photos)} WebP файлов в {folder}: {', '.join(photo_names)}"))

                    # определяем цвета по фото

                    for photo_file in photos:
                        if is_mostly_white(photo_file):
                            self.stdout.write(self.style.WARNING(f"  Пропущено (слишком белое): {photo_file.name}"))
                            continue

                        rgb = get_dominant_color(photo_file)
                        if not rgb:
                            continue

                        css_color_name = rgb_to_color_name(rgb)
                        base_color = normalize_to_basic_color(css_color_name)

                        # игнорируем "под заказ", "цвет на выбор" и т.п.
                        if base_color.lower() in INVALID_COLOR_VALUES:
                            continue
                        colors.add(base_color)
                        photo_color_map.setdefault(base_color, []).append(photo_file)

                        if not first_photo:
                            first_photo = photo_file


                    self.stdout.write(self.style.SUCCESS(f"  Цвета из фото: {', '.join(sorted(colors)) if colors else 'Нет'}"))

                    # --- создаём варианты продукта ---
                    variants = []
                    if colors:
                        self.stdout.write(self.style.SUCCESS(f"  Создаём варианты по цветам: {', '.join(sorted(colors))}"))
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
                                    self.stdout.write(self.style.ERROR(f"  Ошибка при добавлении фото {photo_file.name} для варианта {variant_name}: {str(e)}"))
                                    logger.error(f"Ошибка при добавлении фото {photo_file.name}: {str(e)}")

                            variant.save()
                            variants.append(variant)
                            self.stdout.write(self.style.SUCCESS(f"    └─ Создан вариант: {variant_name} (slug: {slug})"))
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
                                self.stdout.write(self.style.ERROR(f"  Ошибка при добавлении фото {first_photo.name}: {str(e)}"))
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
                            self.stdout.write(self.style.ERROR(f"Ошибка при добавлении главного фото {first_photo.name}: {e}"))
                            logger.error(f"Ошибка при добавлении главного фото {first_photo.name}: {e}")
                    else:
                        self.stdout.write(self.style.WARNING(f"Нет подходящего главного фото в {folder} (все белые или отсутствуют)"))

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
                            rgb = get_dominant_color(photo_file)
                            photo_color_name = None
                            if rgb:
                                css_color_name = rgb_to_color_name(rgb)
                                photo_color_name = normalize_to_basic_color(css_color_name)
                                if photo_color_name.lower() in INVALID_COLOR_VALUES:
                                    photo_color_name = None

                            with open(photo_file, "rb") as f:
                                if photo_color_name:
                                    target_variant = next(
                                        (v for v in variants if f"{product_name} ({photo_color_name})" == v.variant_name),
                                        None
                                    )
                                    if target_variant:
                                        ProductPhoto.objects.create(
                                            product=product,
                                            product_var=target_variant,
                                            photo=File(f, name=photo_file.name)
                                        )
                                        self.stdout.write(self.style.SUCCESS(
                                            f"Фото добавлено к варианту {target_variant.variant_name}: {photo_file.name}"
                                        ))
                                    else:
                                        # Если нет варианта с таким цветом — добавляем ко всем
                                        for variant in variants:
                                            ProductPhoto.objects.create(
                                                product=product,
                                                product_var=variant,
                                                photo=File(f, name=photo_file.name)
                                            )
                                        self.stdout.write(self.style.SUCCESS(
                                            f"Фото добавлено ко всем вариантам (цвет не найден): {photo_file.name}"
                                        ))
                                else:
                                    # Цвет не определён или rgb == None → добавляем ко всем
                                    for variant in variants:
                                        ProductPhoto.objects.create(
                                            product=product,
                                            product_var=variant,
                                            photo=File(f, name=photo_file.name)
                                        )
                                    self.stdout.write(self.style.SUCCESS(
                                        f"Фото добавлено ко всем вариантам (цвет не определён): {photo_file.name}"
                                    ))

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
            cleaned = re.sub(r'[^\d\.,\-]', '', s)
            # Если одновременно есть и запятая, и точка, предполагаем, что точка — разделитель тысяч -> удалить точки
            if '.' in cleaned and ',' in cleaned:
                cleaned = cleaned.replace('.', '')
                cleaned = cleaned.replace(',', '.')
            else:
                # заменим запятую на точку (десятичный разделитель)
                cleaned = cleaned.replace(',', '.')
                # удалим пробелы (тысячные)
                cleaned = cleaned.replace(' ', '')
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
            m = re.search(r'(\d+)', s.replace('\xa0', ' '))
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
                if "dimensions" in field or field.startswith(("bed_", "seat_")) or field.endswith(("_width", "_height")):
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
                        setattr(variant, field, float(re.sub(r'[^\d.,]', '', str(value)).replace(',', '.')))
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
                        # если есть пробел между цифрами OR есть буквенные символы (₴, руб.) OR есть запятая/точка в числе
                        if re.search(r'\d+\s+\d+', value) or re.search(r'[^\d\.,\s\-]', value):
                            try_decimal = True
                        if re.search(r'[,\.\d]+', value) and any(sym in value for sym in (',', '.')):
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
