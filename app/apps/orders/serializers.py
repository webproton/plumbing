import re
import uuid

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from app.apps.products.models import ProductVariant

from . import services
from .models import Cart, CartItems, Order, OrderItem
from .validators import validate_person_name, validate_phone_number

# ---------------------------------------------------------------------------
# Корзина
# ---------------------------------------------------------------------------


class CartItemSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField(min_value=1, max_value=999)
    product_name = serializers.CharField(source="product.name", read_only=True)
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all(), allow_null=True, required=False)
    # price и variant_price — цена выбранного варианта (раньше price ошибочно брался у первого варианта товара)
    price = serializers.SerializerMethodField()
    variant_price = serializers.DecimalField(
        source="variant.price", max_digits=12, decimal_places=2, read_only=True, default=None
    )
    available = serializers.SerializerMethodField(help_text="Доступно к заказу (остаток минус резерв)")
    photo = serializers.SerializerMethodField()

    class Meta:
        model = CartItems
        fields = (
            "id",
            "variant",
            "price",
            "product",
            "product_name",
            "photo",
            "quantity",
            "variant_price",
            "available",
        )

    def get_price(self, item):
        return item.variant.price if item.variant else None

    def get_available(self, item):
        return item.variant.available_stock if item.variant else None

    def get_photo(self, item):
        if item.variant and item.variant.photo:
            return item.variant.photo.url
        if item.product and item.product.photo:
            return item.product.photo.url
        return None


def _validate_items(items):
    if not items:
        raise serializers.ValidationError("Cart items cannot be empty.")
    for item in items:
        product, variant = item.get("product"), item.get("variant")
        if variant is not None and variant.product_id != product.pk:
            raise serializers.ValidationError(f"Вариант {variant.pk} не принадлежит товару «{product.name}»")
        if variant is None:
            variants = list(product.variants.all()[:2])
            if len(variants) != 1:
                raise serializers.ValidationError(f"Для товара «{product.name}» нужно выбрать вариант")
            item["variant"] = variants[0]
    return items


def _replace_items(cart, items):
    """Корзина приводится ровно к переданному списку (клиент присылает корзину целиком)."""
    merged = {}
    for item in items:
        key = (item["product"].pk, item["variant"].pk)
        merged.setdefault(key, {"product": item["product"], "variant": item["variant"], "quantity": 0})
        merged[key]["quantity"] += item["quantity"]

    existing = {(ci.product_id, ci.variant_id): ci for ci in cart.cart_items.all()}
    for key, ci in existing.items():
        if key not in merged:
            ci.delete()
    for key, data in merged.items():
        ci = existing.get(key)
        if ci:
            if ci.quantity != data["quantity"]:
                ci.quantity = data["quantity"]
                ci.save(update_fields=["quantity"])
        else:
            CartItems.objects.create(cart=cart, **data)


class CartBaseSerializer(serializers.ModelSerializer):
    cart_uuid = serializers.UUIDField(required=False, allow_null=True)
    customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "customer", "cart_uuid"]


class CartCreateSerializer(CartBaseSerializer):
    """
    POST /cart/ — создать корзину или синхронизировать существующую.
    Семантика «заменить»: в корзине остаются ровно переданные позиции с переданными количествами
    (раньше количества прибавлялись к существующим и росли при каждой синхронизации).
    """

    cart_items = CartItemSerializer(many=True)

    class Meta(CartBaseSerializer.Meta):
        fields = ["id", "customer", "cart_items", "cart_uuid"]

    def validate_cart_items(self, value):
        return _validate_items(value)

    @transaction.atomic
    def create(self, validated_data):
        items = validated_data.pop("cart_items")
        cart_uuid = validated_data.get("cart_uuid")
        user = self.context["request"].user

        cart = None
        if user.is_authenticated:
            cart = Cart.objects.filter(customer=user, orders=None).order_by("-created_at").first()
            if cart is None and cart_uuid:
                # «забираем» анонимную корзину после входа
                cart = Cart.objects.filter(cart_uuid=cart_uuid, customer=None, orders=None).first()
                if cart:
                    cart.customer = user
                    cart.save(update_fields=["customer"])
        elif cart_uuid:
            cart = Cart.objects.filter(cart_uuid=cart_uuid, customer=None, orders=None).first()

        if cart is None:
            cart = Cart.objects.create(
                cart_uuid=cart_uuid or uuid.uuid4(),
                customer=user if user.is_authenticated else None,
            )
        cart = Cart.objects.select_for_update().get(pk=cart.pk)
        _replace_items(cart, items)
        return cart


class CartItemUpdateSerializer(CartItemSerializer):
    quantity = serializers.IntegerField(min_value=0, max_value=999)


class CartDetailSerializer(CartBaseSerializer):
    """PUT/PATCH /cart/{id}/ — установить количества позиций (0 — удалить позицию)."""

    cart_items = CartItemUpdateSerializer(many=True)

    class Meta(CartBaseSerializer.Meta):
        fields = CartBaseSerializer.Meta.fields + ["cart_items"]

    @transaction.atomic
    def update(self, instance, validated_data):
        existing = list(instance.cart_items.all())
        for item in validated_data.get("cart_items", []):
            variant = item.get("variant")
            ci = next(
                (
                    c
                    for c in existing
                    if c.product_id == item["product"].pk and (variant is None or c.variant_id == variant.pk)
                ),
                None,
            )
            if ci is None:
                continue
            if item["quantity"] == 0:
                ci.delete()
            else:
                ci.quantity = item["quantity"]
                ci.save(update_fields=["quantity"])
        return instance


# ---------------------------------------------------------------------------
# Заказы
# ---------------------------------------------------------------------------


class OrderItemSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(read_only=True)
    price = serializers.DecimalField(source="unit_price", max_digits=12, decimal_places=2, read_only=True)
    total = serializers.DecimalField(source="line_total", max_digits=14, decimal_places=2, read_only=True)
    photo = serializers.SerializerMethodField()
    variant = serializers.SerializerMethodField()

    class Meta:
        model = OrderItem
        fields = ["name", "sku", "photo", "quantity", "price", "total", "product_id", "variant"]

    def get_photo(self, item):
        if item.variant.photo:
            return item.variant.photo.url
        if item.product and item.product.photo:
            return item.product.photo.url
        return None

    def get_variant(self, item):
        return {"id": item.variant_id, "price": item.unit_price}


class OrderListSerializer(serializers.ModelSerializer):
    number_products = serializers.SerializerMethodField()
    list_of_product_images = serializers.SerializerMethodField()
    can_be_canceled = serializers.SerializerMethodField()
    status_order_display = serializers.CharField(source="get_status_order_display", read_only=True)
    payment_status_display = serializers.CharField(source="get_payment_status_display", read_only=True)
    payment_type_display = serializers.CharField(source="get_payment_type_display", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "list_of_product_images",
            "customer_name",
            "customer_id",
            "email",
            "creation_date",
            "total_price",
            "number_products",
            "status_order",
            "payment_status",
            "can_be_canceled",
            "payment_status_display",
            "status_order_display",
            "payment_type_display",
        )

    def get_number_products(self, obj):
        return sum((i.quantity for i in obj.items.all()), 0)

    def get_list_of_product_images(self, obj):
        result = []
        for item in list(obj.items.all())[:5]:
            photo = OrderItemSerializer().get_photo(item) or "/placeholder.jpg"
            result.append({"photo": photo, "product_id": item.product_id, "variant_id": item.variant_id})
        return result

    def get_can_be_canceled(self, obj):
        request = self.context.get("request")
        return bool(
            request
            and obj.customer_id == request.user.pk
            and obj.payment_status == Order.PAYMENT_STATUS.waiting_for_payment
            and obj.status_order == Order.STATUS.in_processing
        )


class OrderDetailSerializer(serializers.ModelSerializer):
    number_order = serializers.CharField(source="id", read_only=True)
    list_of_products = OrderItemSerializer(source="items", many=True, read_only=True)
    payment_type_display = serializers.CharField(source="get_payment_type_display", read_only=True)
    status_order_display = serializers.CharField(source="get_status_order_display", read_only=True)

    class Meta:
        model = Order
        fields = [
            "customer_name",
            "customer",
            "address",
            "total_price",
            "status_order",
            "status_order_display",
            "payment_status",
            "creation_date",
            "city",
            "department_number",
            "comment",
            "payment_type",
            "number_order",
            "list_of_products",
            "email",
            "payment_type_display",
        ]


class OrderCreateSerializer(serializers.ModelSerializer):
    """
    Оформление заказа по cart_uuid. Корзина выбирается только по UUID
    (поле `cart` с числовым id удалено — по нему можно было оформить чужую корзину).
    """

    cart_uuid = serializers.UUIDField(write_only=True)
    customer_name = serializers.CharField(required=False, allow_blank=True)
    telegram = serializers.CharField(required=False, allow_blank=True, write_only=True)
    whatsapp = serializers.CharField(required=False, allow_blank=True, write_only=True)
    payment_type = serializers.ChoiceField(choices=Order.PAYMENT_CHOICES, default="full")
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            "id",
            "cart_uuid",
            "customer_name",
            "telegram",
            "whatsapp",
            "address",
            "phone_number",
            "email",
            "city",
            "department_number",
            "comment",
            "payment_type",
            "total_price",
            "items",
        ]
        read_only_fields = ["id", "total_price", "items"]

    def validate_cart_uuid(self, cart_uuid):
        user = self.context["request"].user
        owner = Q(customer=None) | Q(customer=user) if user.is_authenticated else Q(customer=None)
        cart = Cart.objects.filter(owner, cart_uuid=cart_uuid, orders=None).first()
        if not cart:
            raise serializers.ValidationError("Корзина не найдена или заказ по ней уже оформлен")
        return cart

    def validate_customer_name(self, value):
        user = self.context["request"].user
        value = (value or "").strip()
        if not value and user.is_authenticated:
            value = f"{user.first_name} {user.last_name}".strip()
        if not value:
            raise serializers.ValidationError("Укажите имя получателя")
        return validate_person_name(value)

    def validate_phone_number(self, value):
        return validate_phone_number(value)

    def validate_comment(self, value):
        if value and re.search(r"https?://", value):
            raise serializers.ValidationError("В комментарии не допускаются ссылки.")
        return value

    def validate(self, data):
        if "customer_name" not in data:
            data["customer_name"] = self.validate_customer_name("")
        return data

    def create(self, validated_data):
        user = self.context["request"].user
        cart = validated_data.pop("cart_uuid")
        order = services.create_order_from_cart(cart, user=user, **validated_data)
        if user.is_authenticated:
            _remember_contacts(user, validated_data)
        return order


def _remember_contacts(user, data):
    """Сохраняем контакты из заказа в профиль, чтобы не вводить их повторно."""
    fields = {k: data.get(k) for k in ("telegram", "whatsapp", "phone_number", "city") if data.get(k)}
    changed = [f for f, v in fields.items() if hasattr(user, f) and getattr(user, f) != v]
    for f in changed:
        setattr(user, f, fields[f])
    if changed:
        user.save(update_fields=changed)
    profile = getattr(user, "profile", None)
    if profile is not None and fields:
        for f, v in fields.items():
            setattr(profile, f, v)
        profile.save()
