"""Загрузка фото товаров по ссылкам поставщика (в фоне)."""

import logging
from io import BytesIO

from django.core.files.base import ContentFile
from PIL import Image

from app.apps.products.models import Product, ProductPhoto, ProductVariant
from app.core.http import FetchError, fetch

logger = logging.getLogger(__name__)

MAX_PHOTOS = 10
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


def download_product_photos(variant_id: int, urls: list[str]) -> int:
    """Скачивает фото, только если у товара ещё нет ни одного (не дублируем при повторных импортах)."""
    variant = ProductVariant.objects.select_related("product").filter(pk=variant_id).first()
    if variant is None:
        return 0
    product = variant.product
    if product.photo or product.photos.exists():
        return 0

    saved = 0
    for url in urls[:MAX_PHOTOS]:
        try:
            result = fetch(url, max_bytes=MAX_PHOTO_BYTES)
        except FetchError as exc:
            logger.info("Фото %s не загружено: %s", url, exc)
            continue
        ext = _image(result.content)
        if ext is None:
            logger.info("По ссылке %s не изображение", url)
            continue
        name = f"{product.slug or product.pk}-{saved + 1}.{ext}"
        if saved == 0:
            product.photo.save(name, ContentFile(result.content), save=False)
            Product.objects.filter(pk=product.pk).update(photo=product.photo.name)
        else:
            ProductPhoto.objects.create(
                product=product, product_var=variant, photo=ContentFile(result.content, name=name)
            )
        saved += 1
    return saved
