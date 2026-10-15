from django.conf import settings
from django.core.files.storage import FileSystemStorage


def private_storage():
    """Хранилище файлов, которые не раздаются nginx'ом (накладные поставщиков). Отдаются только через API."""
    return FileSystemStorage(location=str(settings.PRIVATE_MEDIA_ROOT), base_url=None)
