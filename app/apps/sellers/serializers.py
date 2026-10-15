from rest_framework import serializers

from app.apps.accounts.serializers import UserSerializer  # если есть

from .models import Seller, Shop


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = [
            "id",
            "description",
            "logo",
            "banner",
            "active",
            "address",
            "seller",  # можно скрыть на фронте, если не нужен
        ]
        read_only_fields = ["seller"]


class SellerListSerializer(serializers.ModelSerializer):
    shop = ShopSerializer(read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)

    class Meta:
        model = Seller
        fields = [
            "id",
            "shop_name",
            "slug",
            "user_email",
            "is_approved",
            "verified",
            "commission_percent",
            "created_at",
            "shop",
        ]
        read_only_fields = ["id", "created_at", "slug", "user_email"]


class SellerDetailSerializer(serializers.ModelSerializer):
    shop = ShopSerializer()
    user = UserSerializer(read_only=True)  # если есть UserSerializer

    class Meta:
        model = Seller
        fields = [
            "id",
            "user",
            "shop_name",
            "slug",
            "is_approved",
            "verified",
            "commission_percent",
            "edrpou",
            "bank_account",
            "created_at",
            "shop",
        ]
        read_only_fields = ["id", "created_at", "slug", "user"]


class SellerCreateUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seller
        fields = [
            "shop_name",
            "edrpou",
            "bank_account",
            "commission_percent",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        # комиссию площадки устанавливает только администратор
        if not (request and request.user.is_superuser):
            self.fields["commission_percent"].read_only = True

    def validate_shop_name(self, value):
        if (
            Seller.objects.filter(shop_name__iexact=value)
            .exclude(pk=self.instance.pk if self.instance else None)
            .exists()
        ):
            raise serializers.ValidationError("Магазин с таким названием уже существует.")
        return value
