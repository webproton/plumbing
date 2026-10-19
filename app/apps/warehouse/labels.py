"""
Этикетки со штрихкодом (PDF): термопринтер 58×40 мм (одна на странице) или лист A4 (3×8 по 70×37 мм).
Штрихкод — EAN-13, если код настоящий EAN (13 цифр с верной контрольной), иначе Code128.
"""

from io import BytesIO

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import code128
from reportlab.graphics.barcode.eanbc import Ean13BarcodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from .pdf import _register_font

SIZES = {"thermal": (58 * mm, 40 * mm), "a4": (70 * mm, 37 * mm)}
A4_COLS, A4_ROWS = 3, 8


def is_ean13(code: str) -> bool:
    if len(code) != 13 or not code.isdigit():
        return False
    total = sum(int(d) * (3 if i % 2 else 1) for i, d in enumerate(code[:12]))
    return (10 - total % 10) % 10 == int(code[12])


def _wrap(text: str, font: str, size: float, width: float, lines: int) -> list[str]:
    words, out, line = text.split(), [], ""
    for word in words:
        candidate = f"{line} {word}".strip()
        if stringWidth(candidate, font, size) <= width:
            line = candidate
            continue
        if line:
            out.append(line)
        line = word
        if len(out) == lines:
            break
    if line and len(out) < lines:
        out.append(line)
    if len(out) == lines and " ".join(out) != " ".join(words):
        while out[-1] and stringWidth(out[-1] + "…", font, size) > width:
            out[-1] = out[-1][:-1]
        out[-1] += "…"
    return out


def _barcode(c, code: str, x: float, y: float, width: float, height: float, font: str):
    if is_ean13(code):
        widget = Ean13BarcodeWidget(code[:12])
        widget.barHeight = height - 3 * mm
        bounds = widget.getBounds()
        w, h = bounds[2] - bounds[0], bounds[3] - bounds[1]
        scale = min(width / w, height / h)
        drawing = Drawing(w * scale, h * scale, transform=[scale, 0, 0, scale, 0, 0])
        drawing.add(widget)
        renderPDF.draw(drawing, c, x + (width - w * scale) / 2, y)
        return
    # тихие зоны по краям (10 модулей) — без них дешёвые сканеры не читают код
    probe = code128.Code128(code, barWidth=1, barHeight=height, quiet=True)
    bar = code128.Code128(code, barWidth=min(1.2, width / probe.width), barHeight=height - 3 * mm, quiet=True)
    bar.drawOn(c, x + (width - bar.width) / 2, y + 3 * mm)
    c.setFont(font, 6.5)
    c.drawCentredString(x + width / 2, y + 0.5 * mm, code)


def _label(c, variant, x, y, w, h, shop: str):
    font = _register_font()
    pad = 2 * mm
    product = variant.product
    name = variant.variant_name or product.name or ""
    if product.name and variant.variant_name and variant.variant_name != product.name and product.name not in name:
        name = f"{product.name} {variant.variant_name}"

    c.setFont(font, 6)
    if shop:
        c.drawString(x + pad, y + h - pad - 5, shop[:40])
    lines = _wrap(name, font, 7.5, w - 2 * pad, 2)
    top = y + h - pad - (13 if shop else 6)
    c.setFont(font, 7.5)
    for i, line in enumerate(lines):
        c.drawString(x + pad, top - i * 9, line)

    price = f"{variant.price:.2f} ₴".replace(".", ",") if variant.price is not None else ""
    c.setFont(font, 12)
    c.drawRightString(x + w - pad, top - 2 * 9 - 6, price)
    if variant.code:
        c.setFont(font, 6.5)
        c.drawString(x + pad, top - 2 * 9 - 4, f"арт. {variant.code}"[:30])

    code = (variant.barcode or variant.code or "").strip()
    if code:
        _barcode(c, code, x + pad, y + pad, w - 2 * pad, h * 0.42, font)


def generate_labels(variants, *, size: str = "thermal", copies: int = 1, shop: str = "") -> bytes:
    buffer = BytesIO()
    w, h = SIZES.get(size, SIZES["thermal"])
    items = [v for v in variants for _ in range(copies)]
    if size == "a4":
        c = canvas.Canvas(buffer, pagesize=A4)
        page_w, page_h = A4
        margin_x = (page_w - A4_COLS * w) / 2
        margin_y = (page_h - A4_ROWS * h) / 2
        for i, variant in enumerate(items):
            slot = i % (A4_COLS * A4_ROWS)
            if i and slot == 0:
                c.showPage()
            col, row = slot % A4_COLS, slot // A4_COLS
            _label(c, variant, margin_x + col * w, page_h - margin_y - (row + 1) * h, w, h, shop)
    else:
        c = canvas.Canvas(buffer, pagesize=(w, h))
        for i, variant in enumerate(items):
            if i:
                c.showPage()
            _label(c, variant, 0, 0, w, h, shop)
    c.save()
    return buffer.getvalue()
