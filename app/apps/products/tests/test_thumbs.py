"""Уменьшенные копии фото: делаются один раз, по размеру и в WebP; чужие пути и битые файлы — безопасно."""

from io import BytesIO
from pathlib import Path

import pytest
from django.conf import settings
from django.test import Client
from PIL import Image


def _png(path: Path, size=(1200, 900)):
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGBA", size, (200, 30, 30, 255)).save(path, "PNG")


def test_thumb_made_once_smaller_and_webp():
    _png(Path(settings.MEDIA_ROOT) / "products" / "pump-1.png")
    client = Client()
    resp = client.get("/media/thumbs/400/products/pump-1.png.webp")
    assert resp.status_code == 200 and resp["Content-Type"] == "image/webp"
    image = Image.open(BytesIO(b"".join(resp.streaming_content)))
    assert image.format == "WEBP" and max(image.size) == 400

    cached = Path(settings.MEDIA_ROOT) / "thumbs" / "400" / "products" / "pump-1.png.webp"
    assert cached.is_file()
    stamp = cached.stat().st_mtime_ns
    assert client.get("/media/thumbs/400/products/pump-1.png.webp").status_code == 200
    assert cached.stat().st_mtime_ns == stamp  # второй раз не пересоздаётся


@pytest.mark.parametrize(
    "url",
    [
        "/media/thumbs/333/products/pump-1.png.webp",  # размер не из списка
        "/media/thumbs/400/products/pump-1.png",  # без .webp
        "/media/thumbs/400/../config/settings.py.webp",  # выход из папки media
        "/media/thumbs/400/products/missing.png.webp",
        "/media/thumbs/400/thumbs/400/products/pump-1.png.webp.webp",  # копия от копии
    ],
)
def test_bad_requests_are_404(url):
    _png(Path(settings.MEDIA_ROOT) / "products" / "pump-1.png")
    assert Client().get(url).status_code == 404


def test_broken_image_falls_back_to_original():
    broken = Path(settings.MEDIA_ROOT) / "products" / "broken.png"
    broken.parent.mkdir(parents=True, exist_ok=True)
    broken.write_bytes(b"not an image")
    resp = Client().get("/media/thumbs/160/products/broken.png.webp")
    assert resp.status_code == 302 and resp["Location"].endswith("/media/products/broken.png")
