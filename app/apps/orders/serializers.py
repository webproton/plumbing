import re
import uuid
# from django.db.models import Q, F
from rest_framework import serializers
from django.db.models import Sum
from app.apps.accounts.models import Profile
from .models import Order, CartItems, Cart
from app.apps.products.models import ProductVariant #, Product
from .utils import validate_phone_number
# import json



class CartBaseSerializer(serializers.ModelSerializer):
    cart_uuid = serializers.UUIDField(required=False, allow_null=True)
    customer = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = Cart
        fields = ["id", "customer", "cart_uuid"]

class CartItemSerializer(serializers.ModelSerializer):
    quantity = serializers.IntegerField()
    product_name = serializers.CharField(source='product.name', read_only=True)
    # product_photo = serializers.ImageField(source='product.photo', read_only=True)
    price = serializers.SerializerMethodField()
    # product_variant_id = serializers.IntegerField(source='product.variants.first.id', read_only=True)
    variant = serializers.PrimaryKeyRelatedField(queryset=ProductVariant.objects.all(), allow_null=True)
    variant_price = serializers.DecimalField(source='variant.price', max_digits=10, decimal_places=2, read_only=True)

    photo = serializers.SerializerMethodField()  # 👈 заменили product_photo / variant_photo на универсальное поле
    class Meta:
        model = CartItems
        fields = ('id','variant', 'price','product','product_name', 'photo', 'quantity','variant_price')

    def get_price(self, cart_item):
        # Получаем цену первого варианта
        first_variant = cart_item.product.variants.first()
        if first_variant:
            return first_variant.price
        return None
    

    def get_photo(self, cart_item):
        """Возвращает фото варианта, если есть, иначе — фото продукта"""
        variant = cart_item.variant
        if variant and variant.photo:
            return variant.photo.url
        if cart_item.product and cart_item.product.photo:
            return cart_item.product.photo.url
        return None  # можно тут дефолт поставить, типа "/media/placeholder.jpg"
    

class CartCreateSerializer(CartBaseSerializer):

    cart_items = CartItemSerializer(many=True, partial=True)
    

    class Meta:
        model = Cart
        fields = ["id", "customer", "cart_items", "cart_uuid"]

    def validate_cart_items(self, value):

        # print(value,"value in validate cart items")
        if not isinstance(value, list):
            raise serializers.ValidationError("Cart items must be a list.")
        
        if not value:
            raise serializers.ValidationError("Cart items cannot be empty.")
        
        for item in value:
            product = item.get("product")
            variant = item.get("variant")
            if not product:
                raise serializers.ValidationError("Each cart item must have a valid product.")
                    # 🧠 получаем объект варианта, если это просто ID
            if isinstance(variant, int):
                try:
                    variant = ProductVariant.objects.get(id=variant)
                    item["variant"] = variant  # заменяем на объект для дальнейшего использования
                except ProductVariant.DoesNotExist:
                    raise serializers.ValidationError(f"Variant ID {variant} does not exist.")

            if variant and not product.variants.filter(id=variant.id).exists():
                raise serializers.ValidationError(
                    f"Вариант ID {variant.id} не принадлежит продукту '{product.name}'"
                )

        return value


    def update(self, instance, validated_data):
        cart_items_data = validated_data.get("cart_items", [])
        self._add_cart_items(instance, cart_items_data)

        if instance.cart_items.count() == 0:
            instance.delete()

        return instance


    def create(self, validated_data):
        """
        Создаёт новую корзину или добавляет товары в существующую активную корзину пользователя.
        """
        cart_items = validated_data.pop("cart_items", [])
        cart_uuid = validated_data.get("cart_uuid")
        user = self.context["request"].user

        # Проверяем существующую корзину
        if user.is_authenticated:
            # Находим активную корзину для авторизованного пользователя
            existing_cart = Cart.objects.filter(customer=user, orders=None).first()
        else:
            # Находим корзину для анонимного пользователя с указанным cart_uuid
            existing_cart = Cart.objects.filter(cart_uuid=cart_uuid, customer=None, orders=None).first()

        if existing_cart:
            # Если корзина уже существует, добавляем товары в неё
            self._add_cart_items(existing_cart, cart_items)
            return existing_cart

        # Создаём новую корзину
        new_cart_uuid = cart_uuid or uuid.uuid4()
        new_cart = Cart.objects.create(cart_uuid=new_cart_uuid,
            customer=user if user.is_authenticated else None,
        )
        self._add_cart_items(new_cart, cart_items)
        return new_cart

    def _add_cart_items(self, cart, cart_items):
        """
        Добавляет товары в корзину или обновляет их количество.
        """
        for cart_item in cart_items:
            product = cart_item.get("product")
            quantity = cart_item.get("quantity", 0)
            variant = cart_item.get("variant")

            if not product or quantity <= 0:
                continue
            # Проверка: принадлежит ли вариант этому продукту
            if variant and not ProductVariant.objects.filter(id=variant.id, product=product).exists():
                continue

            # Поиск по product и variant (если вариант выбран)
            query_kwargs = {'product': product}
            if variant:
                query_kwargs['variant'] = variant

            # Проверяем, есть ли товар в корзине
            # existing_item = cart.cart_items.filter(**query_kwargs).first()
            # existing_item = cart.cart_items.filter(product=product).first()
                  #  Ищем по product и variant, учитывая None отдельно
            if variant is not None:
                existing_item = cart.cart_items.filter(product=product, variant=variant).first()
            else:
                existing_item = cart.cart_items.filter(product=product, variant__isnull=True).first()

            if existing_item:
                # Обновляем количество товара, если он уже есть в корзине
                existing_item.quantity += quantity
                existing_item.save()
            else:
                # Добавляем новый товар в корзину
                CartItems.objects.create(cart=cart, product=product, variant=variant, quantity=quantity)
                # CartItems.objects.create(cart=cart, product=product, quantity=quantity)

class CartDetailSerializer(CartBaseSerializer):
    cart_items = CartItemSerializer(many=True, partial=True)

    class Meta(CartBaseSerializer.Meta):
        fields = CartBaseSerializer.Meta.fields + ["cart_items"]
        
    def update(self, instance, validated_data):
        cart_items_data = validated_data.pop("cart_items", [])
        
        # Создаем словарь для быстрого поиска CartItem по продукту
        product_to_cart_item_map = {
            item.product.id: item for item in instance.cart_items.all()
        }

        updated_cart_items = []
        for item_data in cart_items_data:
            product = item_data.get("product")
            quantity = item_data.get("quantity")

            # Получаем CartItem по продукту
            cart_item = product_to_cart_item_map.get(product.id) if product else None
            if cart_item:
                updated_cart_items.append({
                    "id": cart_item.id,
                    "quantity": quantity,
                })

        # Теперь обновляем элементы корзины по ID
        cart_items_dict = {item.id: item for item in instance.cart_items.all()}

        for item_data in updated_cart_items:
            cart_item_id = item_data["id"]
            quantity = item_data["quantity"]

            if cart_item_id in cart_items_dict and quantity is not None:
                cart_item = cart_items_dict[cart_item_id]
                if quantity > 0:
                    cart_item.quantity = quantity
                    cart_item.save()
                else:
                    # Удаляем элемент корзины, если количество <= 0
                    cart_item.delete()

        return instance

class OrderSerializer(serializers.ModelSerializer):

    class Meta:
        model = Order
        fields = ["customer_name", "customer" ,"address", "total_price", "status_order", "payment_status","creation_date",'city', 'department_number','comment','payment_type']

class OrderListSerializer(serializers.ModelSerializer):
    # List of orders with fields: customer name, date, total price, number_dishes(total number), status +
    number_products = serializers.SerializerMethodField()
    list_of_product_images = serializers.SerializerMethodField()
    can_be_canceled = serializers.SerializerMethodField()
    status_order_display = serializers.CharField(source='get_status_order_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    class Meta:
        model = Order
        fields = (
            'id',
            'list_of_product_images',
            'customer_name',
            'customer_id',
            'email',
            'creation_date',
            'total_price',
            'number_products',
            'status_order',
            'payment_status',
            'can_be_canceled',
            'payment_status_display',
            'status_order_display',
            "payment_type_display"
            )

    def get_number_products(self, obj):
        # Получаем общее количество товаров в корзине через аннотирование
        total_quantity = CartItems.objects.filter(cart=obj.cart).aggregate(total=Sum('quantity'))['total']
        return total_quantity if total_quantity else 0

    def get_list_of_product_images(self, obj):
            # Берем первые 5 товаров и возвращаем их фото
            cart_items = obj.cart.cart_items.select_related('product')
            result = []
            for item in cart_items[:5]:
                product = item.product
                variant = item.variant


                # Если у варианта есть фото — берем его
                if variant and variant.photo:
                    photo_url = variant.photo.url
                elif product and product.photo:
                    photo_url = product.photo.url
                else:
                    photo_url = '/placeholder.jpg'

                result.append({
                    # 'photo': product.photo.url if product.photo else '/placeholder.jpg',
                    'photo': photo_url,
                    'product_id': product.id,
                    'variant_id': item.variant.id if item.variant else None,  
                })
            return result
  
    def get_can_be_canceled(self, obj):
        request = self.context.get('request')
        return (
            obj.customer == request.user and 
            obj.payment_status == Order.PAYMENT_STATUS.waiting_for_payment
        )

class OrderDetailSerializer(OrderSerializer):
    # Order details with fields: customer name, address, date, total price, number of orders(id order), status, list of products.

    list_of_products = serializers.SerializerMethodField()
    number_order = serializers.CharField(source="id", read_only=True)
    payment_type_display = serializers.CharField(source='get_payment_type_display', read_only=True)
    class Meta(OrderSerializer.Meta):
        fields = OrderSerializer.Meta.fields + ["number_order", "list_of_products","email","payment_type_display"]


    def get_list_of_products(self, obj):
        cart_items = obj.cart.cart_items.select_related('product', 'variant')
        

        result = []
        for item in cart_items:
            product = item.product
            variant = item.variant
            price = variant.price if variant else 0


            # Берём фото варианта, если он есть; иначе — фото продукта
            photo_url = None
            if variant and variant.photo:
                photo_url = variant.photo.url
            elif product.photo:
                photo_url = product.photo.url

            result.append({
                'name': product.name,
                'photo': photo_url,
                # 'photo': product.photo.url if product.photo else None,
                'quantity': item.quantity,
                'price': price,
                'total': price * item.quantity,
                'product_id': product.id,
                'variant': {
                    'id': variant.id,
                    'price': price,
                } if variant else None
            })

        return result


class OrderCreateSerializer(OrderSerializer):
    # Создание заказа с полями: список продуктов, адрес, имя клиента
    cart_items = CartItemSerializer(many=True, source='cart.cart_items.all', read_only=True)
    cart_uuid = serializers.UUIDField(write_only=True, source="cart.cart_uuid")
    cart = serializers.PrimaryKeyRelatedField(
        queryset=Cart.objects.filter(orders=None),
        write_only=True,
        required=False
    )
    telegram = serializers.CharField(required=False, allow_blank=True)
    whatsapp = serializers.CharField(required=False, allow_blank=True)
    customer_name = serializers.CharField(
    required=False,  # не требуется DRF
    allow_blank=True,  # пустое разрешаем
    validators=[],
            )
    
    payment_type = serializers.ChoiceField(
        choices=Order.PAYMENT_CHOICES, 
        # required=True, 
        default='full'
    )
    class Meta:
        model = Order
        fields = ["id","customer_name","telegram","whatsapp", "cart_uuid", "address","phone_number", "email", "cart","cart_items", "city", "department_number", "comment","payment_type"]
        extra_kwargs = {
            'telegram': {'write_only': True},
            'whatsapp': {'write_only': True}
        }


    def validate(self, data):
        """
        Метод для проверки данных перед созданием заказа.
        1. Проверка, что корзина указана.
        2. Проверка, что корзина не пуста.
        3. Проверка, что корзина принадлежит текущему пользователю.
        """
        user = self.context["request"].user 
        cart = data.get("cart")

        if isinstance(cart, dict) and "cart_uuid" in cart:
            cart = cart["cart_uuid"]  # Извлекаем объект модели Cart

        if not isinstance(cart, Cart):
            raise serializers.ValidationError("Ошибка получения корзины.")

        data["cart"] = cart  # Подменяем на объект модели
        
        # Проверка на наличие товаров в корзине
        if not cart.cart_items.exists():
            raise serializers.ValidationError("Корзина пуста, невозможно создать заказ.")


        # Проверка на наличие уже существующего заказа с такой корзиной
        existing_order = Order.objects.filter(cart=cart, status_order=Order.STATUS.in_processing).first()
        if existing_order:
            raise serializers.ValidationError("Заказ для этой корзины уже существует.")
            
        # Дополнительная валидация для поля comment
        comment = data.get('comment', '')
        if comment and re.search(r'http[s]?://', comment):
            raise serializers.ValidationError("В комментарии не допускаются ссылки.")

        return data

    def validate_customer_name(self, value):
        user = self.context["request"].user
        value = value.strip()

        if user.is_authenticated:
            if not value:
                first_name = getattr(user, "first_name", "")
                last_name = getattr(user, "last_name", "")
                value = f"{first_name} {last_name}".strip()
                if not value:
                    raise serializers.ValidationError("Необходимо указать имя клиента.")
        else:
            if not value:
                raise serializers.ValidationError("Для анонимного пользователя обязательно укажите имя клиента.")

        # Проверка, что имя состоит только из букв
        if not value.replace(' ', '').isalpha():
            raise serializers.ValidationError("Имя клиента должно содержать только буквы.")

        return value
    
    def validate_cart_uuid(self, cart_uuid):
        user = self.context["request"].user

        # Для анонимного пользователя cart_uuid может быть не привязан к конкретному пользователю, поэтому проверяем отдельно
        if user.is_authenticated:
            cart = Cart.objects.filter(cart_uuid=cart_uuid, customer=user, orders=None).order_by("created_at").first()
        else:
            cart = Cart.objects.filter(cart_uuid=cart_uuid, orders=None).order_by("created_at").first()

        if not cart:
            raise serializers.ValidationError(
                "Cart not found or already associated with an order"
            )
        return cart
        
    

    
    def validate_phone_number(self, value):
        return validate_phone_number(value)
    
    def create(self, validated_data):
        """
        Метод для создания нового заказа.
        1. Создаем заказ с полученными данными.
        2. Рассчитываем общую стоимость заказа на основе корзины.
        3. Сохраняем заказ в базе данных.
        """
        # Получаем корзину из данных
        cart = validated_data['cart']

        telegram = validated_data.pop('telegram', None)
        whatsapp = validated_data.pop('whatsapp', None)
        cart = cart
        phone_number = validated_data.get("phone_number")
        customer_name = validated_data.get("customer_name")
        email = validated_data.get('email', '')
        address = validated_data.get('address')
        city = validated_data.get("city")
        # region = validated_data.get("region")
        # сountry = validated_data.get("country")
        # zip_code = validated_data.get("zip_code")
        user = self.context['request'].user
        department_number = validated_data.get("department_number")
        comment = validated_data.get("comment")
        
        # Если пользователь анонимный, то устанавливаем значение customer = None
        if user.is_authenticated:
            customer = user
        else:
            customer = None
            
        # Определение данных для доставки
        # Создание нового заказа
        order = Order.objects.create(
            customer = customer,
            customer_name=customer_name,
            address=address,
            cart=cart,  # Связываем корзину с заказом
            phone_number=phone_number,
            email=email,  # Письмо если указано
            city=city,
            # region=region,
            department_number=department_number,
            comment=comment,
            telegram=telegram,
            whatsapp=whatsapp,
            # country=сountry,
            # zip_code=zip_code,
            payment_type=validated_data.get('payment_type', 'full')  # ✅ добавляем

        )
        # После создания заказа рассчитываем общую стоимость
        order.total_price = cart.calculate_total_price()  # Предполагается, что есть метод для подсчета стоимости
        order.save()

        # Обновляем данные пользователя, если он авторизован
        # После обновления данных пользователя
        # Подготовим данные профиля
        profile_data = {
            "telegram": telegram,
            "whatsapp": whatsapp,
            "phone_number": phone_number,
            "city": city,
            # "region": region,
}

        # Для авторизованного пользователя
        if user.is_authenticated:
            updated = False
            for field, value in profile_data.items():
                if value and getattr(user, field, None) != value:
                    setattr(user, field, value)
                    updated = True
            if updated:
                user.save()
                # print("User updated:", profile_data)

            # Сохраняем данные в профиле
            if hasattr(user, 'profile'):
                profile = user.profile
                for field, value in profile_data.items():
                    if value:
                        setattr(profile, field, value)
                profile.save()
                # print("Profile updated:", profile_data)

        # Для анонимного пользователя — создаем "профиль без пользователя"
        else:
            Profile.objects.create(
                user=None,
                email=email,
                **{k: v for k, v in profile_data.items() if v}  # сохраняем только заполненные поля
            )
            # print("Anonymous profile created:", profile_data)


        return order
