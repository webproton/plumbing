import re
from decimal import Decimal, InvalidOperation
from pathlib import Path
import math
from PIL import Image
from django.conf import settings
from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
import logging
import colorsys

try:
    import numpy as np
    HAS_NUMPY = True
except Exception:
    HAS_NUMPY = False

from webcolors import rgb_to_name, hex_to_rgb
from colorthief import ColorThief

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

SPECIAL_COLORS = {
        (22, 12, 11): "Эбеновое (чёрное дерево)",   # #160c0b
        (119, 58, 42): "Махагон",                   # #773a2a
        (183, 183, 178): "Светло-серый",            # #b7b7b2
        (180, 126, 83): "Терракот",                 # #b47e53
        (183, 131, 87): "Дуб мёдовый",              # #b78357
        (45, 12, 7): "Венге",                       # #2d0c07
        (135, 72, 55): "Орех тёмный",               # #874837
        (66, 28, 18): "Шоколад",                    # #421c12
        (187, 132, 86): "Карамель",                 # #bb8456
        (196, 196, 194): "Светло-серый",            # #c4c4c2
        (193, 154, 116): "Бук натуральный",         # #c19a74
        (202, 134, 86): "Дуб янтарный",             # #ca8656
        (193, 111, 59): "Терракотовый",             # #c16f3b
        (176, 179, 175): "Тёпло-серый",             # #b0b3af
        (146, 118, 78): "Дуб табак",                # #92764e
        (183, 129, 86): "Дуб коньячный",            # #b78156
        (178, 122, 80): "Каштан натуральный",       # #b27a50
        (222, 197, 168): "Ясень выбеленный",        # #dec5a8
        (141, 61, 36): "Красное дерево",            # #8d3d24
        (149, 64, 38): "Палисандр",                 # #954026
        (49, 35, 32): "Венге шоколадный",           # #312320
        (165, 115, 75): "Орех светлый",             # #a5734b
    }

FURNITURE_COLOR_MAP = {
    # Древесные оттенки
    "венге": "brown",
    "эбеновое (чёрное дерево)": "black",
    "орех": "brown",
    "дуб": "brown",
     "махагон": "brown",
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

def _is_near_rgb(rgb_norm, target_rgb, threshold=12):
    """Сравнивает RGB с допуском"""
    r, g, b = [int(x * 255) for x in rgb_norm]
    tr, tg, tb = target_rgb
    dist = math.sqrt((r-tr)**2 + (g-tg)**2 + (b-tb)**2)
    return dist <= threshold

def is_mahogany(rgb):
    target = (119, 58, 42)
    threshold = 10  # допустимое отклонение
    r, g, b = [int(x*255) for x in rgb]
    distance = ((r - target[0])**2 + (g - target[1])**2 + (b - target[2])**2)**0.5
    return distance <= threshold

def rgb_to_basic_color(rgb):


    # rgb — tuple 0..255 or 0..1? у тебя 0..255 в текущем вызове, так что нормализуем
    if max(rgb) > 1:  # если передали в 0..255
        rgb_norm = (rgb[0]/255, rgb[1]/255, rgb[2]/255)
    else:
        rgb_norm = rgb

    # ✅ Проверяем спец-цвета по близости
    for rgb255, name in SPECIAL_COLORS.items():
        if _is_near_rgb(rgb_norm, rgb255, threshold=15):
            return name

    # # специальные цвета (диапазоны)
    # # Эбеновое дерево / чёрный: target #160c0b (22,12,11)
    # if _is_near_rgb(rgb_norm, (22, 12, 11), threshold=14):
    #     return "Эбеновое (чёрное дерево)"

    # # Махагон / тёплый тёмный коричневый: target #773a2a (119,58,42)
    # if _is_near_rgb(rgb_norm, (119, 58, 42), threshold=16):
    #     return "Махагон"
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
    # Специальный цвет #773a2a
    # Специальный цвет махагон (допускаем +-5 в RGB)
    # в начале функции
    # if is_mahogany((r, g, b)):
    #     return "Махагон"

    
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


def rgb_to_basic_color1(rgb):
    """
    Преобразует RGB в расширенный набор базовых и интерьерных цветов (~22 цвета).
    """
    r, g, b = [x / 255 for x in rgb]
    h, s, v = colorsys.rgb_to_hsv(r, g, b)
    h_deg = h * 360

    # Очень темные — венге, мокко, тёмно-коричневые
    if v < 0.15:
        return "Венге"

    # Слабо насыщенные — серые / пастельные / светлые
    if s < 0.25:
        if v > 0.85:
            return "Белый"
        elif v < 0.3:
            return "Черный"
        else:
            return "Серый"
        
    # Специальный цвет #773a2a
    if (r, g, b) == (119/255, 58/255, 42/255):  # #773a2a
        return "Махагон"
    # Красный спектр
    if 0 <= h_deg < 15 or 345 <= h_deg <= 360:
        if v < 0.4:
            return "Бордовый"
        return "Красный"

    # Терракотовый / Масала / Оранжевый
    elif 15 <= h_deg < 40:
        if v < 0.5:
            return "Масала"  # тёплый коричневый
        return "Оранжевый"

    # Желтый / Лайм / Салатовый
    elif 40 <= h_deg < 70:
        if g > r and g > b:
            return "Салатовый"
        elif h_deg > 55:
            return "Лайм"
        return "Желтый"

    # Зеленый спектр
    elif 70 <= h_deg < 165:
        if v < 0.35:
            return "Тёмно-зелёный"
        return "Зеленый"

    # Бирюзовый / Мятный / Голубой
    elif 165 <= h_deg < 200:
        if h_deg < 180:
            return "Бирюзовый"
        else:
            return "Мятный"

    # Синий / Индиго
    elif 200 <= h_deg < 260:
        if v < 0.35:
            return "Тёмно-синий"
        elif 220 <= h_deg < 240:
            return "Индиго"
        return "Синий"

    # Фиолетовый / Лавандовый / Бордовый
    elif 260 <= h_deg < 290:
        if v < 0.35:
            return "Бордовый"
        elif s < 0.5:
            return "Лавандовый"
        return "Фиолетовый"

    # Розовый / Пудровый / Фуксия
    elif 290 <= h_deg < 345:
        if s < 0.5:
            return "Пудровый"
        elif h_deg > 320:
            return "Фуксия"
        return "Розовый"

    # Коричневые оттенки мебели
    if 15 <= h_deg < 45 and v < 0.4:
        return "Орех"
    if 20 <= h_deg < 35 and v < 0.3:
        return "Кофе"
    if 15 <= h_deg < 35 and v < 0.2:
        return "Мокко"

    # На всякий случай
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
         "Махагон": "Коричневый", 
    }
    return mapping.get(name, name)

def rgb_to_hsv_tuple(rgb):
    """rgb tuple 0-255 -> hsv (h in [0,1], s in [0,1], v in [0,1])"""
    r, g, b = rgb
    return colorsys.rgb_to_hsv(r / 255.0, g / 255.0, b / 255.0)

def is_too_dark_rgb(rgb, avg_thresh=0.12):
    """Проверка слишком тёмного цвета. avg_thresh — порог для value (0..1)."""
    _, s, v = rgb_to_hsv_tuple(rgb)
    # Используем v (value) для оценки яркости
    return v < avg_thresh

def is_too_light_rgb(rgb, light_thresh=0.95):
    """Проверка слишком светлого (практически белого)."""
    _, s, v = rgb_to_hsv_tuple(rgb)
    return v > light_thresh

def kmeans_numpy(pixels, k=4, max_iter=12):
    """Простой k-means на numpy. pixels shape (n,3), dtype float."""
    n = pixels.shape[0]
    # Инициализируем центры случайными пикселями
    idx = np.random.choice(n, size=min(k, n), replace=False)
    centers = pixels[idx].copy()
    for it in range(max_iter):
        # расстояния (n, k)
        dists = np.linalg.norm(pixels[:, None, :] - centers[None, :, :], axis=2)
        labels = np.argmin(dists, axis=1)
        moved = False
        for j in range(centers.shape[0]):
            members = pixels[labels == j]
            if len(members) == 0:
                # реинициализация центра
                centers[j] = pixels[np.random.randint(0, n)]
                moved = True
            else:
                new_center = members.mean(axis=0)
                if not np.allclose(new_center, centers[j]):
                    centers[j] = new_center
                    moved = True
        if not moved:
            break
    return centers, labels

def get_palette_from_colorthief(path, palette_size=6, quality=5):
    """Fallback: вернуть палитру из ColorThief"""
    try:
        ct = ColorThief(str(path))
        pal = ct.get_palette(color_count=palette_size, quality=quality)
        return pal
    except Exception:
        return []

def choose_best_cluster(centers, labels, pixels):
    """Оценка кластеров: берем долю пикселей и среднюю насыщенность;
       возвращаем RGB центра выбранного кластера (int tuple)."""
    # centers: (k,3) float, pixels (n,3), labels (n,)
    k = centers.shape[0]
    best_score = -1
    best_rgb = None

    # вычислим hsv для всех пикселей
    # нормализуем пиксели для hsv
    pix_norm = pixels / 255.0
    maxc = pix_norm.max(axis=1)
    minc = pix_norm.min(axis=1)
    diff = maxc - minc
    # saturation
    s_all = np.where(maxc == 0, 0, diff / maxc)
    v_all = maxc

    for j in range(k):
        members_idx = (labels == j)
        cnt = members_idx.sum()
        if cnt == 0:
            continue
        size_ratio = cnt / pixels.shape[0]  # доля
        s_mean = s_all[members_idx].mean() if cnt > 0 else 0.0
        v_mean = v_all[members_idx].mean() if cnt > 0 else 0.0

        # фильтрация: пропускаем слишком тёмные или слишком светлые кластеры
        if v_mean < 0.12:  # слишком темные → вероятно тени
            continue
        if v_mean > 0.98 and s_mean < 0.08:  # почти белый & слабая насыщенность -> фон
            continue

        # score = доля * (0.5 + насыщенность) -> увеличиваем шанс ярких цветов
        score = size_ratio * (0.4 + s_mean)
        # небольшая прибавка если насыщенность значительно высокая
        score += 0.1 * s_mean

        if score > best_score:
            best_score = score
            best_rgb = centers[j]

    if best_rgb is None:
        # если ничего не прошло фильтр — выбрать кластер с наибольшей долей, но избегая ультра-тёмных
        counts = np.array([ (labels==j).sum() for j in range(centers.shape[0]) ])
        if counts.sum() == 0:
            return None
        j = np.argmax(counts)
        candidate = centers[j]
        # если candidate слишком тёмный — возвращаем None
        _, _, v = colorsys.rgb_to_hsv(candidate[0]/255., candidate[1]/255., candidate[2]/255.)
        if v < 0.06:
            return None
        best_rgb = candidate

    # возвращаем int RGB tuple
    r, g, b = [int(round(x)) for x in best_rgb]
    r = max(0, min(255, r)); g = max(0, min(255, g)); b = max(0, min(255, b))
    return (r, g, b)
def get_dominant_color_improved(image_path, k=4, sample_pixels=8000, resize_max=500, center_crop=True):
    """
    Надёжное определение доминантного цветa:
    - если есть numpy: делаем k-means по пикселям (сэмплинг) и выбираем кластер по доле и насыщенности
    - если numpy отсутствует: fallback на ColorThief палитру с фильтрацией
    Параметры можно тонко настроить.
    Возвращает (r,g,b) или None.
    """
    # 1) Открываем и подготавливаем изображение
    try:
        img = Image.open(image_path).convert("RGB")
    except Exception:
        return None

    # центрируем (исключить рамки/фон)
    if center_crop:
        w, h = img.size
        crop_factor = 0.85  # берем центральные 85% по каждой стороне
        nw = int(w * crop_factor)
        nh = int(h * crop_factor)
        left = (w - nw) // 2
        top = (h - nh) // 2
        img = img.crop((left, top, left + nw, top + nh))

    # уменьшаем для производительности
    w, h = img.size
    scale = 1.0
    if max(w, h) > resize_max:
        scale = resize_max / max(w, h)
        img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)

    if HAS_NUMPY:
        # 2) получаем numpy массив пикселей
        ar = np.asarray(img, dtype=np.uint8)
        pixels = ar.reshape((-1, 3)).astype(np.float32)

        n = pixels.shape[0]
        if n == 0:
            return None

        # 3) сэмплируем до sample_pixels
        if n > sample_pixels:
            idx = np.random.choice(n, sample_pixels, replace=False)
            sample = pixels[idx]
        else:
            sample = pixels

        # 4) запускаем kmeans (k=min(k, sample_size))
        k_used = min(k, max(1, int(len(sample) / 50)))  # небольшой адаптивный выбор k
        k_used = min(k_used, 8)
        try:
            centers, labels = kmeans_numpy(sample, k=k_used, max_iter=12)
        except Exception:
            # если kmeans упал — fallback на ColorThief
            centers = None
            labels = None

        if centers is not None:
            # Но labels относились к sample — нужно получить метки для всего набора.
            # Для оценки долей используем sample labels и sample size -> нормально.
            rgb = choose_best_cluster(centers, labels, sample)
            if rgb:
                return rgb

        # fallback: попытаться использовать ColorThief палитру
    # Если нет numpy или кластеризация не дала результатов — fallback
    pal = get_palette_from_colorthief(image_path, palette_size=6, quality=5)
    # отфильтруем палитру: убираем слишком тёмные/светлые
    valid = [c for c in pal if (not is_too_dark_rgb(c)) and (not is_too_light_rgb(c))]
    if valid:
        # выбрать самый насыщенный из валидных или первый
        def sat(c):
            _, s, v = rgb_to_hsv_tuple(c)
            return s
        valid_sorted = sorted(valid, key=lambda c: (sat(c), sum(c)/3.0), reverse=True)
        return valid_sorted[0]
    # если и этого нет — вернём None
    return None

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

def get_dominant_color(path, quality=10, palette_size=6):
    ct = ColorThief(str(path))
    palette = ct.get_palette(color_count=palette_size, quality=quality)
    # palette = [(r, g, b), ...]
    
    # отфильтруем слишком тёмные/светлые
    valid_colors = [c for c in palette if is_valid_color(c)]
    if not valid_colors:
        return None
    
    # вернём первый валидный (или можно выбрать по яркости)
    return valid_colors[0]

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


