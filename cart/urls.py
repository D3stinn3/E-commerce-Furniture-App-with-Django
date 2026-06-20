from django.urls import path
from .import views

urlpatterns = [
    path('store', views.store, name='store'),
    path('search/',views.search,name='search'),
    path('cart', views.view_cart, name='view_cart'),
    path('add/<int:product_id>/', views.add, name='add'),
    path('remove/<int:item_id>/', views.remove, name='remove'),
    path('load-more/', views.load_more_products, name='load_more_products'),
    path('product', views.product_list,name='product'),
    path('checkout/', views.checkout, name='checkout'),
    path('payment/callback/', views.paystack_callback, name='paystack_callback'),
    path('order-success/<int:order_id>/', views.order_success, name='order_success'),
    path('order/<int:order_id>/receipt/', views.download_receipt, name='download_receipt'),
]
