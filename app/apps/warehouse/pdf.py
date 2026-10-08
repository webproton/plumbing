# app/apps/warehouse/pdf.py
from io import BytesIO

from django.conf import settings
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

_FONT = "DejaVuSans"
_FONT_PATH = settings.BASE_DIR / "app" / "fonts" / "DejaVuSans-Bold.ttf"


def _register_font():
    if _FONT not in pdfmetrics.getRegisteredFontNames() and _FONT_PATH.exists():
        pdfmetrics.registerFont(TTFont(_FONT, str(_FONT_PATH)))
    return _FONT if _FONT in pdfmetrics.getRegisteredFontNames() else "Helvetica"


def generate_invoice_pdf(document) -> bytes:
    """PDF накладной в памяти. Файл не сохраняется в публичный MEDIA — отдаётся через API."""
    buffer = BytesIO()
    c = canvas.Canvas(buffer)
    font = _register_font()
    c.setFont(font, 12)
    c.drawString(60, 800, f"Накладная #{document.document_number or document.id}")
    c.setFont(font, 10)
    c.drawString(60, 782, f"Продавец: {document.seller.shop_name}")
    if document.supplier:
        c.drawString(60, 766, f"Поставщик: {document.supplier.name}")

    y = 736
    for m in document.stock_movements.select_related("variant").order_by("id"):
        if y < 60:
            c.showPage()
            c.setFont(font, 10)
            y = 800
        c.drawString(60, y, f"{m.variant.variant_name or m.variant_id} — {m.quantity} × {m.price_per_unit or 0}")
        y -= 16
    c.save()
    return buffer.getvalue()
