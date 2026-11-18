"""Загрузка фото товаров по ссылкам поставщика (в фоне).
Диск сервера не резиновый: фото уменьшаются до 1600 px и сохраняются JPEG (~100–250 КБ вместо мегабайт),
не больше 6 на товар; если свободно меньше 3 ГБ — не скачиваем вовсе (позиции прайса показывают фото по ссылке)."""

import logging
import shutil
from io import BytesIO

from django.conf import settings
from django.core.files.base import ContentFile
from PIL import Image, ImageOps

from app.apps.products.models import Product, ProductPhoto, ProductVariant
from app.core.http import FetchError, fetch

logger = logging.getLogger(__name__)

MAX_PHOTOS = 6
MAX_SIDE = 1600
JPEG_QUALITY = 82
MIN_FREE_BYTES = 3 * 1024**3  # меньше 3 ГБ свободно — фото не качаем
MAX_PHOTO_BYTES = 10 * 1024 * 1024
EXTENSIONS = {"JPEG": "jpg", "PNG": "png", "WEBP": "webp", "GIF": "gif"}


def _image(content: bytes) -> str | None:
    try:
        with Image.open(BytesIO(content)) as img:
            fmt = img.format
            img.verify()
    except Exception:  # noqa: BLE001 — Pillow бросает разные ошибки на битых/опасных файлах
        return None
    return EXTENSIONS.get(fmt)


def shrink(content: bytes) -> bytes | None:
    """Фото → JPEG не больше 1600 px по длинной стороне (прозрачный фон — белый). None — не изображение."""
    try:
        with Image.open(BytesIO(content)) as img:
            img = ImageOps.exif_transpose(img)
            if img.mode in ("RGBA", "LA", "P"):
                img = img.convert("RGBA")
                background = Image.new("RGB", img.size, "white")
                background.paste(img, mask=img.getchannel("A"))
                img = background
            else:
                img = img.convert("RGB")
            img.thumbnail((MAX_SIDE, MAX_SIDE), Image.Resampling.LANCZOS)
            out = BytesIO()
            img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
            return out.getvalue()
    except Exception:  # noqa: BLE001 — битый/опасный файл
        return None


def disk_full() -> bool:
    try:
        return shutil.disk_usage(settings.MEDIA_ROOT).free < MIN_FREE_BYTES
    except OSError:
        return False


def download_product_photos(variant_id: int, urls: list[str]) -> int:
    """Скачивает фото, только если у товара ещё нет ни одного (не дублируем при повторных импортах)."""
    variant = ProductVariant.objects.select_related("product").filter(pk=variant_id).first()
    if variant is None:
        return 0
    product = variant.product
    if product.photo or product.photos.exists():
        return 0

    if disk_full():
        logger.warning("Мало места на диске — фото товара %s не скачиваем", product.pk)
        return 0
    saved = 0
    for url in urls[:MAX_PHOTOS]:
        try:
            result = fetch(url, max_bytes=MAX_PHOTO_BYTES)
        except FetchError as exc:
            logger.info("Фото %s не загружено: %s", url, exc)
            continue
        if _image(result.content) is None or (small := shrink(result.content)) is None:
            logger.info("По ссылке %s не изображение", url)
            continue
        name = f"{product.slug or product.pk}-{saved + 1}.jpg"
        if saved == 0:
            product.photo.save(name, ContentFile(small), save=False)
            Product.objects.filter(pk=product.pk).update(photo=product.photo.name)
        else:
            ProductPhoto.objects.create(
                product=product, product_var=variant, photo=ContentFile(small, name=name)
            )
        saved += 1
    return saved
