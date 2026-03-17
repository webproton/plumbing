from django.shortcuts import get_object_or_404, redirect
from rest_framework import viewsets, permissions, mixins, status
from django_filters import rest_framework as filters
from rest_framework.response import Response
from django.core.cache import cache
from rest_framework.pagination import PageNumberPagination
from django.db.models import Avg
from rest_framework.decorators import action
from app.apps.products.serializers import (
    CategorySerializer,
    BrandSerializer,
    WishlistSerializer,
    ProductListSerializer,
    ProductDetailSerializer,
    ProductSetLikesSerializer
)
from app.apps.products.models import (

    Product,
    Category,
    Brand,
    ProductVariant,
    Wishlist
)
from .filters import ProductFilters
from django.urls import reverse
from django.db import transaction, IntegrityError
from django.utils import timezone

from django.db.models import Prefetch


import logging

logger = logging.getLogger(__name__)

class ProductPagination(PageNumberPagination):
    page_size = 20  # сколько товаров на странице
    page_size_query_param = 'page_size'
    max_page_size = 100


class NewProducts(viewsets.GenericViewSet,mixins.ListModelMixin):
    serializer_class = ProductListSerializer
    lookup_field = "pk"

    permission_classes = [permissions.AllowAny]


    def get_queryset(self):
        # пробуем достать из кэша
        cached = cache.get("new_products")
        if cached:
            return cached

        qs = Product.objects.order_by('-id')[:6]

        # сохраняем в кэш на 5 минут
        cache.set("new_products", qs, timeout=300)
        return qs


class BrandList(mixins.ListModelMixin,viewsets.GenericViewSet,mixins.RetrieveModelMixin):
    serializer_class = BrandSerializer
    permissions_classes = [permissions.AllowAny]
    lookup_field = "pk"
    
    def get_queryset(self):
        # Extract category_id from query parameters
        category_id = self.kwargs['pk']

        if category_id is not None:
            return Brand.objects.filter(products__category__id=category_id).distinct()

        else:
            return Brand.objects.none()

    def retrieve(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        serializer = self.serializer_class(queryset, many=True)
        return Response(serializer.data)


class CategoryList(viewsets.GenericViewSet, mixins.ListModelMixin, mixins.RetrieveModelMixin):
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]
   
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Category.objects.all()
        return queryset.distinct()


    def get_serializer_class(self):
        return self.serializer_class


class ProductListView(viewsets.GenericViewSet,mixins.ListModelMixin,mixins.RetrieveModelMixin):
    serializer_class = ProductListSerializer
    filterset_class = ProductFilters
    lookup_field = "slug"
    permission_classes = [permissions.AllowAny]
    pagination_class = ProductPagination
    # permission_classes = [permissions.IsAdminUser]
    search_fields = ["name"]
    filter_backends = (filters.DjangoFilterBackend,)
    ordering_fields =["average_price"]
    ordering =["-average_price"]

    def get_queryset(self):
        # Формируем ключ кэша на основе параметров запроса
        query_params = self.request.GET.urlencode()
        cache_key = f"product_list_{query_params}"

        # Пробуем достать из кэша
        cached = cache.get(cache_key)
        if cached:
            return cached
        
        # Предзагрузка вариантов продуктов для оптимизации запросов
        queryset = Product.objects.prefetch_related(
            Prefetch('variants', queryset=ProductVariant.objects.order_by('id'), to_attr='filtered_variants')
        ).annotate(average_price=Avg("variants__price")).order_by("average_price").distinct()

    
        # Apply the filters to the queryset
        # фильтр по параметрах продукта ProductVariant и возвр продукты!! 
        filterset = self.filterset_class(self.request.GET, queryset=queryset)
        if filterset.is_valid():
            queryset = filterset.qs
            
            
        # Применяем сортировку
        ordering = self.request.query_params.get('ordering', None)
        if ordering:
            queryset = queryset.order_by(ordering)
            
        # Сохраняем в кэш на 5 минут
        cache.set(cache_key, queryset, timeout=300)
        return queryset


    def get_serializer_class(self):
        """on assignment. in the detailed information
        about the restaurant,
        you need to show an additional field"""
        if self.action == "retrieve":
            return ProductDetailSerializer
        # if self.action == "like_product":
        #     return ProductSetLikesSerializer
        return ProductListSerializer
    
    # Опционально: кэшируем сериализованные данные для retrieve
    def retrieve(self, request, *args, **kwargs):
        slug = kwargs.get("slug")
        cache_key = f"product_detail_{slug}"
        cached_data = cache.get(cache_key)
        if cached_data:
            return Response(cached_data)

        instance = self.get_object()
        serializer = self.get_serializer(instance)
        cache.set(cache_key, serializer.data, timeout=300)
        return Response(serializer.data)
    
    # @action(detail=True, methods=['post'])
    # def like_product(self, request, pk=None,):
    #     if not self.request.user.is_authenticated:
    #         # Redirect to login 
    #         return redirect('rest_login')
        
    #     product = get_object_or_404(Product, pk=pk)
    #     user = self.request.user.id
    #     product_id = self.kwargs['pk']
    #     url = reverse("products:product-detail", args=[product_id ])
        
    #     if user in product.like_user:
    #         # User has already liked the dish
    #         return Response({"detail": "You have already liked this product."})
        
    #     product.like_user.append(user)
    #     product.save()
    #     return redirect(url)
    
    def new_products(self,request):
        pass
    


class WishlistViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.DestroyModelMixin,
    viewsets.GenericViewSet
):
    serializer_class = WishlistSerializer
    permission_classes = [permissions.AllowAny]

    def get_queryset(self):
        if self.request.user.is_authenticated:
            return Wishlist.objects.filter(user=self.request.user)
        return Wishlist.objects.none()

    def perform_create(self, serializer):
        if not self.request.user.is_authenticated:
            return Response(
                {"detail": "Anonymous wishlist only in localStorage"},
                status=status.HTTP_403_FORBIDDEN
            )
        serializer.save(user=self.request.user)

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Anonymous wishlist only in localStorage"},
                status=status.HTTP_403_FORBIDDEN
            )

        variant_id = request.data.get("product_variant_id")
        if not variant_id:
            return Response(
                {"detail": "product_variant_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            product_variant = ProductVariant.objects.get(id=variant_id)
        except ProductVariant.DoesNotExist:
            return Response(
                {"detail": "Product variant not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        try:
            with transaction.atomic():
                wishlist, created = Wishlist.objects.select_for_update(nowait=True).get_or_create(
                    user=request.user,
                    product_variant=product_variant,
                    defaults={"added_at": timezone.now()}
                )
                serializer = self.get_serializer(wishlist)
                status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
                return Response(serializer.data, status=status_code)
        except IntegrityError:
            wishlist = Wishlist.objects.filter(
                user=request.user,
                product_variant=product_variant
            ).first()
            if wishlist:
                serializer = self.get_serializer(wishlist)
                return Response(serializer.data, status=status.HTTP_200_OK)
            return Response(
                {"detail": "Не удалось создать запись в избранном"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=['put'], url_path='bulk-update')
    def bulk_update(self, request):
        if not request.user.is_authenticated:
            return Response({"detail": "Login required"}, status=status.HTTP_401_UNAUTHORIZED)

        user = request.user
        data = request.data

        if not isinstance(data, list):
            return Response(
                {"detail": "Data should be a list of items."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            with transaction.atomic():
                # Удаляем существующие записи
                Wishlist.objects.filter(user=user).delete()

                # Формируем новые записи
                new_items = []
                for item in data:
                    if not isinstance(item, dict):
                        continue  # пропустить некорректные элементы
                    variant_id = item.get('product_variant_id')
                    if variant_id:
                        try:
                            product_variant = ProductVariant.objects.get(id=variant_id)
                            new_items.append(Wishlist(user=user, product_variant=product_variant))
                        except ProductVariant.DoesNotExist:
                            continue

                if new_items:
                    Wishlist.objects.bulk_create(new_items, ignore_conflicts=True)

                wishlists = Wishlist.objects.filter(user=user)
                serializer = self.get_serializer(wishlists, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Ошибка при массовом обновлении: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=False, methods=['post'], url_path='clear')
    def clear_wishlist(self, request):
        # print('clear wish list views<<<<<<<<<<<<<<<')
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Только авторизованные пользователи."},
                status=status.HTTP_403_FORBIDDEN
            )
        deleted_count, _ = Wishlist.objects.filter(user=request.user).delete()
        return Response({"detail": f"Удалено {deleted_count} элементов избранного"})

    @action(detail=False, methods=['post'], url_path='merge')
    def merge_wishlist(self, request):
        # print('merge wish list views<<<<<<<<<<<<<<<')
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Только авторизованные пользователи."},
                status=status.HTTP_403_FORBIDDEN
            )

        variant_ids = request.data.get('variant_ids', [])
        if not variant_ids:
            return Response(
                {"detail": "Требуется список variant_ids"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                new_items = []
                for variant_id in variant_ids:
                    try:
                        product_variant = ProductVariant.objects.get(id=variant_id)
                        # Проверяем, нет ли уже записи
                        if not Wishlist.objects.filter(
                            user=request.user,
                            product_variant=product_variant
                        ).exists():
                            new_items.append(Wishlist(
                                user=request.user,
                                product_variant=product_variant,
                                added_at=timezone.now()
                            ))
                    except ProductVariant.DoesNotExist:
                        continue

                if new_items:
                    Wishlist.objects.bulk_create(new_items, ignore_conflicts=True)

                wishlists = Wishlist.objects.filter(user=request.user)
                serializer = self.get_serializer(wishlists, many=True)
                return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response(
                {"detail": f"Ошибка при слиянии избранного: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )











    # =============

