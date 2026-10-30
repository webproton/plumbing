"""
Уменьшенные копии фото для списков и каталога (оригиналы — PNG по 300–700 КБ — грузились долго).

Адрес копии строится из адреса оригинала: /media/products/x.png → /media/thumbs/400/products/x.png.webp.
nginx отдаёт готовый файл сам; если его ещё нет — запрос приходит сюда, копия делается один раз и
сохраняется рядом (media/thumbs/…), дальше её отдаёт nginx. Оригиналы и база не меняются.
"""

import os
import tempfile
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect
from django.views.decorators.http import require_GET
from PIL import Image, ImageOps, UnidentifiedImageError

WIDTHS = {160, 400, 800}
SOURCE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif"}
QUALITY = 80


def thumb_path(width: int, relative: str) -> Path:
    return Path(settings.MEDIA_ROOT) / "thumbs" / str(width) / f"{relative}.webp"


def make_thumb(source: Path, target: Path, width: int) -> None:
    """Копия не больше width×width, с прозрачностью; пишется во временный файл и подменяется целиком."""
    with Image.open(source) as image:
        image = ImageOps.exif_transpose(image)
        image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
        image.thumbnail((width, width), Image.Resampling.LANCZOS)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=target.parent, suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as out:
                image.save(out, "WEBP", quality=QUALITY, method=4)
            os.replace(tmp, target)
        except BaseException:
            Path(tmp).unlink(missing_ok=True)
            raise


@require_GET
def media_thumb(request, width: int, path: str):
    if width not in WIDTHS or not path.endswith(".webp"):
        raise Http404
    relative = path[: -len(".webp")]
    media = Path(settings.MEDIA_ROOT).resolve()
    source = (media / relative).resolve()
    if (
        media not in source.parents
        or source.suffix.lower() not in SOURCE_EXTENSIONS
        or source.is_relative_to(media / "thumbs")
        or not source.is_file()
    ):
        raise Http404
    target = thumb_path(width, relative)
    if not target.is_file():
        try:
            make_thumb(source, target, width)
        except (UnidentifiedImageError, OSError, ValueError):
            return HttpResponseRedirect(f"{settings.MEDIA_URL}{relative}")  # битое фото — показываем как есть
    response = FileResponse(target.open("rb"), content_type="image/webp")
    response["Cache-Control"] = "public, max-age=2592000"
    return response
