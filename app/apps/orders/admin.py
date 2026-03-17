from django.contrib import admin
from .models import Order,CartItems,Cart

class CartItemsInline(admin.TabularInline):
    model = CartItems
    extra = 0



class CartAdmin(admin.ModelAdmin):
    inlines = [CartItemsInline]
    list_display =["id","customer","cart_uuid",'total_price_display']
    
    def total_price_display(self, obj):
        return obj.calculate_total_price()

    total_price_display.short_description = 'Total Price'
    
class OrderAdmin(admin.ModelAdmin):
    list_display =["id","status_order","cart",'total_price']


class CartItemsAdmin(admin.ModelAdmin):
    list_display = ('product','product_id','variant_id', 'quantity','cart','total_price_display')

    def total_price_display(self, obj):
        return obj.total_price

    total_price_display.short_description = 'Total Price'
    
admin.site.register(Order, OrderAdmin)
admin.site.register(CartItems, CartItemsAdmin)
admin.site.register(Cart,CartAdmin)
