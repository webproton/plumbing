from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler

from app.apps.warehouse.stock import StockError


def api_exception_handler(exc, context):
    """
    Стандартный обработчик DRF + доменные ошибки:
    - StockError (нехватка товара и т.п.) → 400 {"detail", "code", ...контекст}
    - django ValidationError из моделей/сервисов → 400 вместо 500
    """
    if isinstance(exc, StockError):
        payload = {"detail": exc.message, "code": exc.code}
        payload.update({k: str(v) for k, v in exc.context.items()})
        return Response(payload, status=status.HTTP_400_BAD_REQUEST)
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"detail": exc.messages}
        return Response(detail, status=status.HTTP_400_BAD_REQUEST)
    return drf_exception_handler(exc, context)
