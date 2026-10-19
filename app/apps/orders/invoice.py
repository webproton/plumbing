"""Счёт на оплату (PDF): реквизиты магазина из настроек, позиции заказа, сумма прописью."""

from decimal import ROUND_HALF_UP, Decimal
from io import BytesIO

from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from app.apps.warehouse.pdf import _register_font

_ONES = {
    "m": ["", "один", "два", "три", "чотири", "п'ять", "шість", "сім", "вісім", "дев'ять"],
    "f": ["", "одна", "дві", "три", "чотири", "п'ять", "шість", "сім", "вісім", "дев'ять"],
}
_TEENS = ["десять", "одинадцять", "дванадцять", "тринадцять", "чотирнадцять", "п'ятнадцять", "шістнадцять",
          "сімнадцять", "вісімнадцять", "дев'ятнадцять"]  # fmt: skip
_TENS = ["", "", "двадцять", "тридцять", "сорок", "п'ятдесят", "шістдесят", "сімдесят", "вісімдесят", "дев'яносто"]
_HUNDREDS = ["", "сто", "двісті", "триста", "чотириста", "п'ятсот", "шістсот", "сімсот", "вісімсот", "дев'ятсот"]
_SCALES = [  # (род, формы 1 / 2–4 / 5+)
    ("f", ("гривня", "гривні", "гривень")),
    ("f", ("тисяча", "тисячі", "тисяч")),
    ("m", ("мільйон", "мільйони", "мільйонів")),
    ("m", ("мільярд", "мільярди", "мільярдів")),
]


def _plural(n: int, forms: tuple[str, str, str]) -> str:
    if n % 100 in range(11, 20):
        return forms[2]
    return forms[0] if n % 10 == 1 else forms[1] if n % 10 in (2, 3, 4) else forms[2]


def _triad(n: int, gender: str) -> list[str]:
    words = [_HUNDREDS[n // 100]]
    rest = n % 100
    if 10 <= rest < 20:
        words.append(_TEENS[rest - 10])
    else:
        words += [_TENS[rest // 10], _ONES[gender][rest % 10]]
    return [w for w in words if w]


def amount_in_words(amount: Decimal) -> str:
    """1143.00 → «Одна тисяча сто сорок три гривні 00 копійок»"""
    amount = Decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    hryvnias, kopecks = int(amount), int((amount - int(amount)) * 100)
    parts, n = [], hryvnias
    for i, (gender, forms) in enumerate(_SCALES):
        triad = n % 1000
        if triad or i == 0:
            words = _triad(triad, gender)
            if i == 0 and not hryvnias:
                words = ["нуль"]
            parts.insert(0, " ".join([*words, _plural(triad, forms)]))
        n //= 1000
        if not n:
            break
    text = " ".join(parts)
    return f"{text[0].upper()}{text[1:]} {kopecks:02d} {_plural(kopecks, ('копійка', 'копійки', 'копійок'))}"


def _wrap_words(text: str, font: str, size: float, width: float) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        candidate = f"{line} {word}".strip()
        if stringWidth(candidate, font, size) <= width or not line:
            line = candidate
        else:
            lines.append(line)
            line = word
    return [*lines, line] if line else lines


def _money(value) -> str:
    return f"{Decimal(value):,.2f}".replace(",", " ").replace(".", ",")


def generate_invoice(order, shop) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    font = _register_font()
    width, height = A4
    left, right = 18 * mm, width - 18 * mm
    y = height - 20 * mm

    def line(label, value):
        nonlocal y
        if value:
            c.setFont(font, 9)
            c.drawString(left, y, label)
            c.drawString(left + 32 * mm, y, value[:95])
            y -= 5 * mm

    line("Постачальник:", shop.legal_name)
    line("ЄДРПОУ / ІПН:", shop.tax_id)
    line("IBAN:", shop.iban)
    line("Банк:", shop.bank_name)
    line("Адреса:", shop.legal_address)
    line("Телефон:", shop.phone)
    y -= 4 * mm

    date = timezone.localtime(order.creation_date).strftime("%d.%m.%Y")
    c.setFont(font, 14)
    c.drawCentredString(width / 2, y, f"Рахунок на оплату № {order.pk} від {date}")
    y -= 10 * mm
    line("Покупець:", order.customer_name)
    line("Телефон:", order.phone_number or "")
    line("Доставка:", order.address)
    y -= 3 * mm

    qty_x, price_x = right - 53 * mm, right - 24 * mm
    c.setFont(font, 9)
    c.line(left, y + 4 * mm, right, y + 4 * mm)
    c.drawString(left, y, "№")
    c.drawString(left + 9 * mm, y, "Товар")
    c.drawRightString(qty_x, y, "К-сть")
    c.drawRightString(price_x, y, "Ціна")
    c.drawRightString(right, y, "Сума")
    y -= 2 * mm
    c.line(left, y, right, y)
    y -= 5 * mm

    name_width = qty_x - 16 * mm - (left + 9 * mm)
    for i, item in enumerate(order.items.all(), start=1):
        lines = _wrap_words(item.name, font, 8.5, name_width)
        if y < 40 * mm:
            c.showPage()
            y = height - 20 * mm
        c.setFont(font, 8.5)
        c.drawString(left, y, str(i))
        for j, part in enumerate(lines[:3]):
            c.drawString(left + 9 * mm, y - j * 4 * mm, part)
        qty = f"{item.quantity.normalize():f}".replace(".", ",")
        c.drawRightString(qty_x, y, qty)
        c.drawRightString(price_x, y, _money(item.unit_price))
        c.drawRightString(right, y, _money(item.line_total))
        y -= max(len(lines[:3]), 1) * 4 * mm + 2 * mm
    c.line(left, y + 2 * mm, right, y + 2 * mm)
    y -= 4 * mm

    total = order.total_price or Decimal(0)
    c.setFont(font, 11)
    c.drawRightString(right, y, f"Всього до сплати: {_money(total)} грн")
    y -= 6 * mm
    c.setFont(font, 9)
    c.drawRightString(right, y, "Без ПДВ" if not shop.vat_payer else f"У т.ч. ПДВ: {_money(total / 6)} грн")
    y -= 8 * mm
    c.drawString(left, y, f"Сума прописом: {amount_in_words(total)}")
    y -= 6 * mm
    c.drawString(left, y, f"Призначення платежу: оплата за товар згідно рахунку № {order.pk} від {date}")
    y -= 6 * mm
    if order.payment_type == "partial":
        c.drawString(left, y, f"Передоплата 50%: {_money((total / 2).quantize(Decimal('0.01')))} грн")
        y -= 6 * mm
    for note in (shop.invoice_note or "").splitlines()[:5]:
        c.drawString(left, y, note[:110])
        y -= 5 * mm
    c.save()
    return buffer.getvalue()
