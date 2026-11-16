"""API списка закупки (кабинет продавца → «Закупка»). Логика — app.apps.warehouse.purchase."""

from decimal import Decimal, InvalidOperation

from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from . import purchase
from .models import PurchaseLine
from .permissions import IsWarehouseStaff, get_active_seller

MAX_LINES_AT_ONCE = 100


def _seller(request):
    seller = get_active_seller(request.user)
    if seller is None:
        raise ValidationError({"detail": _("Список закупки ведёт продавец — войдите как продавец")})
    return seller


def _line(request, pk) -> PurchaseLine:
    return get_object_or_404(PurchaseLine.objects.select_related("purchase_list__seller"), pk=pk, purchase_list__seller=_seller(request))


class PurchaseListView(APIView):
    """GET — текущий список (создаётся сам)."""

    permission_classes = [IsWarehouseStaff]

    def get(self, request):
        return Response(purchase.serialize_list(purchase.current_list(_seller(request), request.user)))


class PurchaseLinesView(APIView):
    """POST {"texts": ["футорки 20 1/2 в — 10 шт", …]} или {"variants": [id, …]} (из остатков) — новые строки."""

    permission_classes = [IsWarehouseStaff]

    def post(self, request):
        plist = purchase.current_list(_seller(request), request.user)
        texts = request.data.get("texts") or ([request.data["text"]] if request.data.get("text") else [])
        if isinstance(texts, str):
            texts = texts.splitlines()
        texts = [str(t) for t in texts if str(t).strip()][:MAX_LINES_AT_ONCE]
        variants = [int(v) for v in (request.data.get("variants") or []) if str(v).isdigit()][:MAX_LINES_AT_ONCE]
        if not texts and not variants:
            raise ValidationError({"texts": _("Напишите, что нужно докупить")})
        created = purchase.add_lines(plist, request.user, texts=texts, variant_ids=variants)
        return Response({"created": [line.pk for line in created], **purchase.serialize_list(plist)}, status=201)


class PurchaseLineView(APIView):
    """PATCH: {"quantity"} | {"variant", "supplier"?, "supplier_name"?, "price"?} | {"item"} | {"clear": true} | {"text"};
    DELETE — убрать строку."""

    permission_classes = [IsWarehouseStaff]

    def patch(self, request, pk):
        line = _line(request, pk)
        data = request.data
        if "quantity" in data:
            try:
                quantity = Decimal(str(data["quantity"]).replace(",", "."))
            except InvalidOperation:
                raise ValidationError({"quantity": _("Количество — число")}) from None
            if quantity <= 0:
                raise ValidationError({"quantity": _("Количество больше нуля")})
            line.quantity = quantity
            line.save(update_fields=["quantity"])
        if data.get("text"):
            query, _quantity, unit = purchase.parse_line(str(data["text"]))
            line.text, line.unit = query[:255] or line.text, unit or line.unit
            line.save(update_fields=["text", "unit"])
        if data.get("clear"):
            purchase.choose(line, clear=True)
        elif data.get("item"):
            purchase.choose(line, item=int(data["item"]))
        elif data.get("variant"):
            supplier = data.get("supplier")
            purchase.choose(
                line,
                variant=int(data["variant"]),
                supplier=int(supplier) if supplier else None,
                supplier_name=str(data.get("supplier_name") or ""),
                price=data.get("price") or None,
            )
        line.refresh_from_db()
        return Response(purchase.serialize_line(line))

    def delete(self, request, pk):
        _line(request, pk).delete()
        return Response(status=204)


class PurchaseLineOptionsView(APIView):
    """GET — чем может быть строка: «як минулого разу», свои товары с ценами поставщиков, позиции прайсов."""

    permission_classes = [IsWarehouseStaff]

    def get(self, request, pk):
        return Response(purchase.options(_line(request, pk), request.user))


class PurchaseAssembleView(APIView):
    """GET — «Зібрати замовлення»: у кого что заказать, суммы, текст для отправки поставщику."""

    permission_classes = [IsWarehouseStaff]

    def get(self, request):
        return Response(purchase.assemble(purchase.current_list(_seller(request), request.user)))


class PurchaseOrderedView(APIView):
    """POST — «Замовлено»: список в архив (по нему потом «як минулого разу»), начинается новый."""

    permission_classes = [IsWarehouseStaff]

    def post(self, request):
        seller = _seller(request)
        plist = purchase.current_list(seller, request.user)
        if not plist.lines.exists():
            raise ValidationError({"detail": _("Список пуст")})
        purchase.mark_ordered(plist)
        return Response(purchase.serialize_list(purchase.current_list(seller, request.user)))
