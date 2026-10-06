# app/apps/warehouse/pdf.py
from reportlab.pdfgen import canvas
from django.conf import settings
import os


def generate_invoice_pdf(document):

    path = os.path.join(settings.MEDIA_ROOT, f"invoice_{document.id}.pdf")

    c = canvas.Canvas(path)

    c.drawString(100, 800, f"Накладная #{document.id}")
    c.drawString(100, 780, f"Продавец: {document.seller}")

    y = 740

    for m in document.stock_movements.all():
        c.drawString(
            100,
            y,
            f"{m.variant} - {m.quantity} x {m.price_per_unit}"
        )
        y -= 20

    c.save()

    return path
