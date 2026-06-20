from django.contrib import admin
from .models import Product, CartItem, Order, OrderItem

# Register your models here.
admin.site.register(Product)
admin.site.register(CartItem)


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    readonly_fields = ('product_title', 'product_price', 'quantity')
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'user', 'total_price', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email', 'paystack_reference')
    readonly_fields = ('user', 'total_price', 'created_at', 'paystack_reference')
    inlines = [OrderItemInline]
