"""
Файлы ранее загруженных накладных лежали в публичном MEDIA_ROOT (раздавались nginx'ом по /media/invoices/…).
Переносим их в PRIVATE_MEDIA_ROOT (путь внутри хранилища не меняется) и считаем SHA-256 для защиты
от повторной загрузки. Идемпотентно: уже перенесённые файлы пропускаются.
"""
import hashlib
import shutil
from pathlib import Path

from django.conf import settings
from django.db import migrations


def forwards(apps, schema_editor):
    InventoryDocument = apps.get_model("warehouse", "InventoryDocument")
    public_root = Path(settings.MEDIA_ROOT)
    private_root = Path(settings.PRIVATE_MEDIA_ROOT)
    moved = missing = 0
    seen = set()
    for doc in InventoryDocument.objects.exclude(file="").iterator():
        src, dst = public_root / doc.file.name, private_root / doc.file.name
        if src.exists() and not dst.exists():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            moved += 1
        if dst.exists() and not doc.file_hash:
            digest = hashlib.sha256(dst.read_bytes()).hexdigest()
            if (doc.seller_id, digest) not in seen:  # дубликаты прошлых загрузок оставляем без хэша
                seen.add((doc.seller_id, digest))
                InventoryDocument.objects.filter(pk=doc.pk).update(file_hash=digest)
        elif not dst.exists():
            missing += 1
    if moved or missing:
        print(f"\n  [warehouse.0016] перенесено файлов: {moved}, не найдено: {missing}")


class Migration(migrations.Migration):

    dependencies = [
        ("warehouse", "0015_invoice_review"),
    ]

    operations = [
        migrations.RunPython(forwards, migrations.RunPython.noop),
    ]
