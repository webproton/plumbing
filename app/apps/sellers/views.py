from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from .models import Seller, Shop
from .permissions import IsSellerOrReadOnly, IsSellerOwner
from .serializers import SellerCreateUpdateSerializer, SellerDetailSerializer, SellerListSerializer, ShopSerializer


class SellerViewSet(viewsets.ModelViewSet):
    """
    Профиль продавца. Создать — может любой авторизованный (один на пользователя, ждёт одобрения админа).
    Удаление через API запрещено: за продавцом склады и история движений (деактивация — через админку).
    """

    queryset = Seller.objects.all()
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def perform_create(self, serializer):
        if Seller.objects.filter(user=self.request.user).exists():
            raise ValidationError({"detail": "У вас уже есть профиль продавца"})
        serializer.save(user=self.request.user, is_approved=False)

    def get_serializer_class(self):
        if self.action in ["list", "my_seller"]:
            return SellerListSerializer
        if self.action in ["retrieve", "dashboard"]:
            return SellerDetailSerializer
        return SellerCreateUpdateSerializer

    def get_permissions(self):
        if self.action in ["create", "my_seller", "dashboard"]:
            return [IsAuthenticated()]
        if self.action in ["update", "partial_update"]:
            return [IsAuthenticated(), IsSellerOwner()]
        if self.action == "approve":
            return [IsAdminUser()]
        return super().get_permissions()

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Seller.objects.all()
        if hasattr(self.request.user, "seller_profile"):
            return Seller.objects.filter(user=self.request.user)
        return Seller.objects.none()

    @action(detail=False, methods=["get"], url_path="my")
    def my_seller(self, request):
        """Получить данные текущего продавца"""
        seller = get_object_or_404(Seller, user=request.user)
        serializer = self.get_serializer(seller)
        return Response(serializer.data)

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def approve(self, request, pk=None):
        """Админ одобряет продавца"""
        seller = self.get_object()
        seller.is_approved = True
        seller.verified = True
        seller.save()
        return Response({"status": "approved"})

    @action(detail=True, methods=["get"])
    def dashboard(self, request, pk=None):
        """Простой дашборд продавца (можно расширить)"""
        seller = self.get_object()
        if request.user != seller.user and not request.user.is_superuser:
            return Response(status=status.HTTP_403_FORBIDDEN)

        data = {
            "shop_name": seller.shop_name,
            "approved": seller.is_approved,
            "commission": seller.commission_percent,
            "created_at": seller.created_at,
            # позже добавишь: orders_count, revenue, products_count и т.д.
        }
        return Response(data)


class ShopViewSet(viewsets.ModelViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer
    permission_classes = [IsAuthenticated, IsSellerOrReadOnly]

    def get_queryset(self):
        if self.request.user.is_superuser:
            return Shop.objects.all()
        if hasattr(self.request.user, "seller_profile"):
            return Shop.objects.filter(seller=self.request.user.seller_profile)
        return Shop.objects.none()

    def perform_create(self, serializer):
        # автоматически привязываем к текущему продавцу
        seller = self.request.user.seller_profile
        serializer.save(seller=seller)
