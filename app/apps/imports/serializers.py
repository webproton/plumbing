import os
from urllib.parse import urlsplit

from django.utils.translation import gettext as _
from rest_framework import serializers

from .connectors import ADAPTERS
from .models import ImportRun, ImportSource, SupplierItem

SOURCE_FILE_EXTENSIONS = {".xml", ".yml", ".csv", ".xlsx", ".xls", ".json", ".txt"}
MAX_SOURCE_FILE = 50 * 1024 * 1024
TEMPLATE_EXTENSIONS = {".xlsx", ".xls", ".csv"}
MAX_TEMPLATE_FILE = 20 * 1024 * 1024
MAX_MAP_KEYS = 40


def _check_file(f, extensions, max_size):
    ext = os.path.splitext(f.name)[1].lower()
    if ext not in extensions:
        raise serializers.ValidationError(
            _("Неподдерживаемый тип файла. Допустимо: {types}").format(types=", ".join(sorted(extensions)))
        )
    if f.size > max_size:
        raise serializers.ValidationError(_("Файл больше {mb} МБ").format(mb=max_size // (1024 * 1024)))
    return f


class ImportSourceSerializer(serializers.ModelSerializer):
    secret = serializers.CharField(write_only=True, required=False, allow_blank=True, max_length=2000)
    clear_secret = serializers.BooleanField(write_only=True, required=False, default=False)
    has_secret = serializers.SerializerMethodField()
    has_file = serializers.SerializerMethodField()
    file_name = serializers.SerializerMethodField()
    supplier_name = serializers.CharField(source="supplier.name", read_only=True, default=None)
    category_name = serializers.CharField(source="category.name", read_only=True, default=None)
    counts = serializers.SerializerMethodField()

    class Meta:
        model = ImportSource
        fields = [
            "id", "name", "kind", "url", "file", "has_file", "file_name", "format",
            "auth_type", "auth_login", "secret", "clear_secret", "has_secret", "adapter", "field_map", "options",
            "currency", "price_mode", "markup_percent", "price_rounding", "category", "category_name",
            "supplier", "supplier_name", "publish_new", "update_prices", "hide_when_unavailable",
            "sync_interval_minutes", "is_active", "last_sync_at", "next_sync_at", "last_status", "last_error",
            "counts", "created_at",
        ]  # fmt: skip
        read_only_fields = ["last_sync_at", "next_sync_at", "last_status", "last_error", "created_at"]
        extra_kwargs = {"file": {"write_only": True, "required": False}}

    def get_has_secret(self, obj):
        return bool(obj.secret_encrypted)

    def get_has_file(self, obj):
        return bool(obj.file)

    def get_file_name(self, obj):
        return os.path.basename(obj.file.name) if obj.file else ""

    def get_counts(self, obj):
        keys = ("total", "new", "linked", "ignored", "missing")
        return {k: getattr(obj, f"n_{k}", None) for k in keys} if hasattr(obj, "n_total") else None

    def validate_file(self, f):
        return _check_file(f, SOURCE_FILE_EXTENSIONS, MAX_SOURCE_FILE) if f else f

    def validate_url(self, url):
        if url and urlsplit(url).scheme not in ("http", "https"):
            raise serializers.ValidationError(_("Поддерживаются только ссылки http:// и https://"))
        return url

    def _check_map(self, value, name):
        if not isinstance(value, dict) or len(value) > MAX_MAP_KEYS:
            raise serializers.ValidationError(_("{name}: ожидается объект «ключ → значение»").format(name=name))
        return value

    def validate_field_map(self, value):
        value = self._check_map(value, "field_map")
        if not all(isinstance(k, str) and isinstance(v, str) and len(v) <= 255 for k, v in value.items()):
            raise serializers.ValidationError(_("field_map: ключи и значения должны быть строками"))
        return {k: v.strip() for k, v in value.items() if v.strip()}

    def validate_options(self, value):
        return self._check_map(value, "options")

    def validate_sync_interval_minutes(self, value):
        if value and not 30 <= value <= 7 * 24 * 60:
            raise serializers.ValidationError(_("Интервал — от 30 минут до 7 дней (0 — только вручную)"))
        return value

    def validate_markup_percent(self, value):
        if not 0 <= value <= 1000:
            raise serializers.ValidationError(_("Наценка — от 0 до 1000 %"))
        return value

    def validate_price_rounding(self, value):
        if not 0 < value <= 1000:
            raise serializers.ValidationError(_("Шаг округления — больше 0 и не больше 1000"))
        return value

    def validate_currency(self, value):
        return value.upper()

    def validate(self, attrs):
        kind = attrs.get("kind", getattr(self.instance, "kind", ImportSource.KIND_FEED))
        url = attrs.get("url", getattr(self.instance, "url", ""))
        has_file = bool(attrs.get("file") or getattr(self.instance, "file", None))
        if kind == ImportSource.KIND_WEB:
            adapter = attrs.get("adapter", getattr(self.instance, "adapter", ""))
            if adapter not in ADAPTERS:
                raise serializers.ValidationError({"adapter": _("Выберите адаптер сайта поставщика")})
        elif kind == ImportSource.KIND_API and not url:
            raise serializers.ValidationError({"url": _("Укажите адрес API")})
        elif kind == ImportSource.KIND_FEED and not url and not has_file:
            raise serializers.ValidationError({"url": _("Укажите ссылку на фид или загрузите файл")})
        return attrs

    def _apply_secret(self, instance, secret, clear):
        if clear:
            instance.secret = ""
        elif secret:
            instance.secret = secret

    def create(self, validated_data):
        secret, clear = validated_data.pop("secret", ""), validated_data.pop("clear_secret", False)
        instance = ImportSource(**validated_data)
        self._apply_secret(instance, secret, clear)
        instance.save()
        return instance

    def update(self, instance, validated_data):
        secret, clear = validated_data.pop("secret", ""), validated_data.pop("clear_secret", False)
        self._apply_secret(instance, secret, clear)
        return super().update(instance, validated_data)


class SupplierItemSerializer(serializers.ModelSerializer):
    variant_name = serializers.SerializerMethodField()
    variant_price = serializers.DecimalField(
        source="variant.price", max_digits=20, decimal_places=2, read_only=True, default=None
    )
    our_price = serializers.SerializerMethodField(help_text="Цена продажи по правилам источника")
    photo = serializers.SerializerMethodField()

    class Meta:
        model = SupplierItem
        fields = [
            "id", "external_id", "sku", "barcode", "name", "brand", "category_name", "url",
            "price", "old_price", "cost", "currency", "quantity", "available", "photo", "params",
            "status", "variant", "variant_name", "variant_price", "our_price", "match_method", "missing", "changed_at",
        ]  # fmt: skip

    def get_variant_name(self, obj):
        v = obj.variant
        return (v.variant_name or v.product.name) if v else None

    def get_our_price(self, obj):
        pricing = self.context.get("pricing")
        value = pricing.sale(obj) if pricing else None
        return str(value) if value is not None else None

    def get_photo(self, obj):
        return obj.photos[0] if obj.photos else None


class ImportRunSerializer(serializers.ModelSerializer):
    source_name = serializers.CharField(source="source.name", read_only=True, default=None)
    created_by_email = serializers.CharField(source="created_by.email", read_only=True, default=None)

    class Meta:
        model = ImportRun
        fields = [
            "id", "kind", "status", "source", "source_name", "file_name", "options", "stats", "error",
            "created_by_email", "created_at", "started_at", "finished_at",
        ]  # fmt: skip


class TemplateUploadSerializer(serializers.Serializer):
    file = serializers.FileField()
    warehouse = serializers.IntegerField(required=False, allow_null=True)
    publish = serializers.BooleanField(required=False, default=False)

    def validate_file(self, f):
        return _check_file(f, TEMPLATE_EXTENSIONS, MAX_TEMPLATE_FILE)


class PublishSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), max_length=500, allow_empty=False)
    category = serializers.IntegerField(required=False, allow_null=True)
    visible = serializers.BooleanField(required=False, allow_null=True, default=None)


class ItemStatusSerializer(serializers.Serializer):
    ids = serializers.ListField(child=serializers.IntegerField(), max_length=1000, allow_empty=False)
    status = serializers.ChoiceField(choices=[SupplierItem.NEW, SupplierItem.IGNORED])


class LinkSerializer(serializers.Serializer):
    item = serializers.IntegerField()
    variant = serializers.IntegerField()
