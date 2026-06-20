from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Product(models.Model):
    img = models.ImageField(upload_to='pics')
    title = models.CharField(max_length=50)
    desc =  models.TextField()
    price = models.IntegerField()
    offer = models.BooleanField(default=False)
    stock = models.PositiveIntegerField(default=0)
    CHOICES = (
        ('Bed', 'Bed'),
        ('Sofa', 'Sofa'),
        ('Table', 'Table'),
        ('Living Room', 'Living Room'),
        ('Bed Room', 'Bed Room'),
        ('Dinning', 'Dinning')
    )

    category = models.CharField(max_length=20, choices=CHOICES)

    @property
    def in_stock(self):
        return self.stock > 0

    def __str__(self):
        return self.title

class CartItem(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=0)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date_added = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.quantity} x {self.product.title}'


class Order(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
    )

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='orders')
    created_at = models.DateTimeField(auto_now_add=True)
    total_price = models.IntegerField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    paystack_reference = models.CharField(max_length=100, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def order_number(self):
        return f'ORD-{self.id:05d}'

    def __str__(self):
        return f'{self.order_number} - {self.user.username}'


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product_title = models.CharField(max_length=50)
    product_price = models.IntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.product_price * self.quantity

    def __str__(self):
        return f'{self.quantity} x {self.product_title}'