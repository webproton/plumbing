from celery import shared_task
from django.core.cache import cache
from django.utils import timezone
from django.utils.translation import gettext as _

from . import services, template
from .models import ImportRun, ImportSource
from .photos import download_product_photos

SYNC_LOCK_TTL = 45 * 60


@shared_task(name="imports.sync_source")
def sync_source_task(source_id: int, run_id: int | None = None):
    run = ImportRun.objects.filter(pk=run_id).first() if run_id else None
    lock = f"imports:sync:{source_id}"
    if not cache.add(lock, 1, timeout=SYNC_LOCK_TTL):
        if run:
            ImportRun.objects.filter(pk=run.pk).update(
                status=ImportRun.FAILED,
                error=_("Синхронизация этого источника уже выполняется"),
                finished_at=timezone.now(),
            )
        return
    try:
        source = ImportSource.objects.select_related("seller__user").filter(pk=source_id).first()
        if source:
            services.sync_source(source, run)
    finally:
        cache.delete(lock)


@shared_task(name="imports.sync_due_sources")
def sync_due_sources():
    """Beat: ставит в очередь источники, у которых подошло время синхронизации."""
    services.fail_stale_runs()
    now = timezone.now()
    for source in services.due_sources(now).exclude(last_status="running"):
        # сразу сдвигаем срок, чтобы следующий тик beat не поставил источник повторно
        services.schedule_next(source, now)
        ImportSource.objects.filter(pk=source.pk).update(next_sync_at=source.next_sync_at)
        sync_source_task.delay(source.pk)


@shared_task(name="imports.apply_template")
def apply_template_task(run_id: int):
    run = ImportRun.objects.select_related("seller__user", "created_by").get(pk=run_id)
    try:
        stats, rows, photos = template.apply(run)
    except Exception as exc:
        ImportRun.objects.filter(pk=run.pk).update(
            status=ImportRun.FAILED,
            error=_("Внутренняя ошибка: {error}").format(error=exc.__class__.__name__),
            finished_at=timezone.now(),
        )
        raise
    run.rows, run.stats = rows, {**run.stats, "result": stats}
    run.status, run.finished_at = ImportRun.DONE, timezone.now()
    run.save(update_fields=["rows", "stats", "status", "finished_at"])
    for variant_id, urls in photos:
        download_photos_task.delay(variant_id, urls)


@shared_task(name="imports.download_photos")
def download_photos_task(variant_id: int, urls: list[str]):
    return download_product_photos(variant_id, urls)
