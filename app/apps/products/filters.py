from django.db.models import Q
from django_filters import rest_framework as filters

from .models import (
    Armrest,
    Ball,
    BedType,
    BodyMaterial,
    Brand,
    Filling,
    Form,
    IncludedItem,
    MaterialProduct,
    MattressBase,
    Mechanism,
    Pattern,
    Product,
    TypeOfProduct,
    UpholsteryMaterial,
)


class NumberInFilter(filters.BaseInFilter, filters.NumberFilter):
    pass


class ProductFilters(filters.FilterSet):
    # категория вместе с подкатегориями: «Велосипеди» → разделы → категории (дерево направлений)
    category = filters.CharFilter(method="category_filter", label="Category")

    brand = filters.ModelMultipleChoiceFilter(
        queryset=Brand.objects.all(), field_name="variants__brand__id", to_field_name="id", label="Brand"
    )

    material = filters.ModelMultipleChoiceFilter(
        queryset=MaterialProduct.objects.all(),
        field_name="variants__material__id",
        to_field_name="id",
        label="Material product",
    )

    search = filters.CharFilter(method="search_filter", label="Search")

    ball = filters.ModelMultipleChoiceFilter(
        queryset=Ball.objects.all(), field_name="variants__ball__id", to_field_name="id", label="Ball valve"
    )

    type_of_product = filters.ModelChoiceFilter(
        field_name="variants__type_of_product",
        queryset=TypeOfProduct.objects.all(),
        to_field_name="id",
        label="Type of Product",
    )

    min_price = filters.NumberFilter(field_name="variants__price", lookup_expr="gte", label="Min price")
    max_price = filters.NumberFilter(field_name="variants__price", lookup_expr="lte", label="Max price")

    # 📏 Габариты
    min_width = filters.NumberFilter(field_name="variants__dimensions_width", lookup_expr="gte")
    max_width = filters.NumberFilter(field_name="variants__dimensions_width", lookup_expr="lte")
    min_height = filters.NumberFilter(field_name="variants__dimensions_height", lookup_expr="gte")
    max_height = filters.NumberFilter(field_name="variants__dimensions_height", lookup_expr="lte")
    min_depth = filters.NumberFilter(field_name="variants__dimensions_depth", lookup_expr="gte")
    max_depth = filters.NumberFilter(field_name="variants__dimensions_depth", lookup_expr="lte")

    # 🛏 Кровать
    min_bed_width = filters.NumberFilter(field_name="variants__bed_width", lookup_expr="gte")
    max_bed_width = filters.NumberFilter(field_name="variants__bed_width", lookup_expr="lte")
    min_bed_length = filters.NumberFilter(field_name="variants__bed_length", lookup_expr="gte")
    max_bed_length = filters.NumberFilter(field_name="variants__bed_length", lookup_expr="lte")
    sleeping_places = filters.NumberFilter(field_name="variants__sleeping_places", lookup_expr="exact")

    # ⚙️ Характеристики

    mechanism = filters.ModelMultipleChoiceFilter(
        queryset=Mechanism.objects.all(), field_name="variants__mechanism__id", to_field_name="id"
    )

    upholstery_materials = filters.ModelMultipleChoiceFilter(
        queryset=UpholsteryMaterial.objects.all(), field_name="variants__upholstery_materials__id", to_field_name="id"
    )
    mattress_base = filters.ModelChoiceFilter(
        queryset=MattressBase.objects.all(), field_name="variants__mattress_base__id", to_field_name="id"
    )
    storage_niche = filters.BooleanFilter(field_name="variants__storage_niche")

    armrests = filters.ModelChoiceFilter(
        queryset=Armrest.objects.all(), field_name="variants__armrests__id", to_field_name="id"
    )
    filling = filters.ModelChoiceFilter(
        queryset=Filling.objects.all(), field_name="variants__filling__id", to_field_name="id"
    )

    bed_type_form = filters.ModelChoiceFilter(
        queryset=Form.objects.all(), field_name="variants__bed_type_form__id", to_field_name="id"
    )

    bed_type = filters.ModelChoiceFilter(
        queryset=BedType.objects.all(), field_name="variants__bed_type__id", to_field_name="id"
    )

    pattern = filters.ModelChoiceFilter(
        queryset=Pattern.objects.all(), field_name="variants__pattern__id", to_field_name="id"
    )

    body_material = filters.ModelChoiceFilter(
        queryset=BodyMaterial.objects.all(), field_name="variants__body_material__id", to_field_name="id"
    )

    included_items = filters.ModelMultipleChoiceFilter(
        queryset=IncludedItem.objects.all(), field_name="variants__included_items__id", to_field_name="id"
    )

    o = filters.OrderingFilter(
        fields=(
            ("name", "Name"),
            ("variants__price", "price"),
        ),
        field_labels={"name": "product name", "variants__price": "price"},
    )

    class Meta:
        model = Product
        fields = [
            "category",
            "brand",
            "material",
            "ball",
            "type_of_product",
            "min_price",
            "max_price",
            "min_width",
            "max_width",
            "min_height",
            "max_height",
            "min_depth",
            "max_depth",
            "min_bed_width",
            "max_bed_width",
            "min_bed_length",
            "max_bed_length",
            "sleeping_places",
            "mechanism",
            "mattress_base",
            "upholstery_materials",
            "storage_niche",
            "armrests",
            "filling",
            "bed_type_form",
            "bed_type",
            "pattern",
            "body_material",
            "included_items",
            "search",
        ]

    def category_filter(self, queryset, name, value):
        return queryset.filter(
            Q(category__slug=value) | Q(category__parent__slug=value) | Q(category__parent__parent__slug=value)
        )

    def search_filter(self, queryset, name, value):
        """Поиск по названию товара/варианта, артикулу и штрихкоду."""
        value = value.strip()
        if not value:
            return queryset
        return queryset.filter(
            Q(name__icontains=value)
            | Q(variants__variant_name__icontains=value)
            | Q(variants__code__iexact=value)
            | Q(variants__barcode__iexact=value)
        ).distinct()
