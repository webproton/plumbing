from django.contrib import admin, messages
from rest_framework.exceptions import ValidationError

from . import services
from .models import Cart, CartItems, Order, OrderItem


class CartItemsInline(admin.TabularInline):
    model = CartItems
    extra = 0
    raw_id_fields = ("product", "variant")


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemsInline]
    list_display = ["id", "customer", "cart_uuid", "created_at"]
    search_fields = ["cart_uuid", "customer__email"]


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    fields = ("name", "sku", "variant", "unit_price", "quantity", "line_total")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "creation_date", "customer_name", "phone_number", "status_order",
                    "payment_status", "stock_state", "total_price", "manager"]
    list_filter = ["status_order", "payment_status", "stock_state", "manager"]
    search_fields = ["id", "customer_name", "phone_number", "email"]
    readonly_fields = ["cart", "customer", "total_price", "stock_state", "creation_date"]
    inlines = [OrderItemInline]
    date_hierarchy = "creation_date"

    def save_model(self, request, obj, form, change):
        """Смена статуса идёт через сервис — он резервирует/списывает/возвращает товар."""
        if change and "status_order" in form.changed_data:
            new_status = obj.status_order
            obj.status_order = form.initial["status_order"]
            super().save_model(request, obj, form, change)
            try:
                services.change_status(obj, new_status, user=request.user)
            except ValidationError as exc:
                self.message_user(request, f"Статус не изменён: {exc.detail}", level=messages.ERROR)
            obj.refresh_from_db()
        else:
            super().save_model(request, obj, form, change)
