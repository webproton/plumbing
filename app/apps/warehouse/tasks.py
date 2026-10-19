import logging
import os

from celery import shared_task
from django.conf import settings
from django.utils.translation import gettext as _

from parsers import ai
from parsers.core.loader import NeedsAI, load_rows

from .models import InventoryDocument
from .services import parse_document

logger = logging.getLogger(__name__)

SPREADSHEETS = {".xlsx", ".xls", ".xml", ".yml"}


@shared_task(name="warehouse.parse_document_ai")
def parse_document_ai_task(document_id: int):
    """Разбор накладной через Claude; результат участвует в выборе лучшего разбора (parsers.pipeline)."""
    document = InventoryDocument.objects.filter(pk=document_id, processed=False).first()
    if document is None:
        return
    InventoryDocument.objects.filter(pk=document.pk).update(ai_status="running", ai_error="")
    path = document.file.path
    rows = None
    if os.path.splitext(path)[1].lower() in SPREADSHEETS:
        try:
            rows = load_rows(path)  # таблицу отправляем текстом: дешевле и точнее, чем файл
        except NeedsAI:
            rows = None
    try:
        result = ai.extract(path, api_key=settings.ANTHROPIC_API_KEY, model=settings.INVOICE_AI_MODEL, rows=rows)
    except ai.AIError as exc:
        InventoryDocument.objects.filter(pk=document.pk).update(ai_status="failed", ai_error=str(exc))
        return
    except Exception as exc:  # noqa: BLE001 — сбой фиксируем на документе, а не теряем в воркере
        logger.exception("ИИ-разбор накладной %s упал", document.pk)
        message = _("Внутренняя ошибка: {error}").format(error=exc.__class__.__name__)
        InventoryDocument.objects.filter(pk=document.pk).update(ai_status="failed", ai_error=message)
        return
    InventoryDocument.objects.filter(pk=document.pk).update(ai_status="done", ai_result=result, ai_error="")
    document.refresh_from_db()
    try:
        parse_document(document)
    except Exception as exc:  # noqa: BLE001
        InventoryDocument.objects.filter(pk=document.pk).update(ai_error=str(exc))
