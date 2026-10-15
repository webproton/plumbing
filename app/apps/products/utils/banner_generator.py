import logging
import os
import random

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)


def rounded_rectangle_mask(size, radius):
    """Создаёт маску для скругления углов"""
    mask = Image.new("L", size, 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle([0, 0, size[0], size[1]], radius=radius, fill=255)
    return mask


def remove_white_background(im, threshold=240):
    """Прозрачный фон для почти белого"""
    im = im.convert("RGBA")
    datas = im.getdata()
    newData = []
    for item in datas:
        if item[0] > threshold and item[1] > threshold and item[2] > threshold:
            newData.append((255, 255, 255, 0))  # прозрачный
        else:
            newData.append(item)
    im.putdata(newData)
    return im


def generate_banner(product):
    try:
        logger.info(f"Генерация баннера для продукта: {product.id} - {product.name}")

        width, height = 968, 200
        radius = 30

        # Цвет фона баннера
        warm_colors = [
            (255, 243, 224),
            (255, 235, 205),
            (255, 228, 196),
            (250, 214, 165),
            (255, 218, 185),
            (255, 222, 173),
            (255, 240, 245),
            (255, 245, 238),
        ]
        bg_color = random.choice(warm_colors)

        # Баннер с альфа-каналом и скругленными углами
        banner = Image.new("RGBA", (width, height), bg_color + (255,))
        mask = rounded_rectangle_mask((width, height), radius)
        banner.putalpha(mask)

        draw = ImageDraw.Draw(banner)

        font_path = os.path.join(settings.BASE_DIR, "fonts", "DejaVuSans-Bold.ttf")
        font_big = ImageFont.truetype(font_path, 20)
        font_small = ImageFont.truetype(font_path, 16)

        # Фото продукта
        photo_size = (160, 160)
        product_x = (width // 2) - photo_size[0] - 20
        product_y = (height - photo_size[1]) // 2

        if product.photo and os.path.exists(product.photo.path):
            product_img_raw = Image.open(product.photo.path)
            product_img = remove_white_background(product_img_raw)
            product_img.thumbnail(photo_size, Image.Resampling.LANCZOS)
            banner.paste(product_img, (product_x, product_y), product_img)
            logger.info("Фото продукта добавлено на баннер")
        else:
            product_img = None
            logger.warning("Фото продукта не найдено или не задано")

        # Текст о скидке и цене
        text_start_x = product_x + photo_size[0] + 30
        discount = getattr(product, "discount", 0)
        variant = product.variants.first()
        price = variant.price if variant else 0
        discounted_price = price * (100 - discount) / 100 if price else 0
        price_text = f"Цена: {discounted_price:.2f} ₴" if discount else f"Цена: {price:.2f} ₴"

        draw.text((text_start_x, 40), f"СКИДКА: {discount}%", fill="red", font=font_big)
        draw.text((text_start_x + 50, 90), f"Товар: {product.name}", fill="black", font=font_big)
        draw.text((text_start_x, 140), price_text, fill="black", font=font_small)

        # Иконки на баннере
        icons_folder = os.path.join(settings.BASE_DIR, "app", "static", "icons")
        if not os.path.exists(icons_folder):
            logger.warning(f"Папка с иконками не найдена: {icons_folder}")
            icon_files = []
        else:
            icon_files = [f for f in os.listdir(icons_folder) if f.endswith(".png")]

        if icon_files:
            random_icons = random.sample(icon_files, min(5, len(icon_files)))
            for icon_name in random_icons:
                icon_path = os.path.join(icons_folder, icon_name)
                icon = Image.open(icon_path).resize((40, 40))
                circle_color = tuple(min(255, c + 40) for c in bg_color) + (180,)
                circle = Image.new("RGBA", (50, 50), (0, 0, 0, 0))
                circle_draw = ImageDraw.Draw(circle)
                circle_draw.ellipse([(0, 0), (49, 49)], fill=circle_color)

                pos_x = random.randint(10, width - 60)
                pos_y = random.randint(10, height - 60)

                banner.paste(circle, (pos_x, pos_y), circle)
                banner.paste(icon, (pos_x + 5, pos_y + 5), icon)
            logger.info("Иконки добавлены на баннер")
        else:
            logger.info("Иконки не добавлены, папка пуста или не найдена")

        # Сохранение баннера
        output_dir = os.path.join(settings.MEDIA_ROOT, "banners")
        os.makedirs(output_dir, exist_ok=True)
        output_path = os.path.join(output_dir, f"{product.id}_banner.png")
        banner.save(output_path, format="PNG")
        logger.info(f"Баннер сохранён: {output_path}")

        return f"/media/banners/{product.id}_banner.png"

    except Exception:
        logger.exception(f"Ошибка при генерации баннера для продукта {getattr(product, 'id', 'unknown')}")
        raise
