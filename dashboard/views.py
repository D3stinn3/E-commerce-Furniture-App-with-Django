import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Sum, Count, F
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from cart.models import Order, OrderItem, Product
from .forms import ProductForm

LOW_STOCK_THRESHOLD = 5


@staff_member_required
def home(request):
    paid_orders = Order.objects.filter(status='paid')
    context = {
        'total_revenue': paid_orders.aggregate(total=Sum('total_price'))['total'] or 0,
        'order_count': paid_orders.count(),
        'product_count': Product.objects.count(),
        'low_stock_count': Product.objects.filter(stock__lte=LOW_STOCK_THRESHOLD).count(),
        'low_stock_threshold': LOW_STOCK_THRESHOLD,
        'recent_orders': paid_orders.select_related('user')[:10],
    }
    return render(request, 'dashboard/home.html', context)


@staff_member_required
def inventory_list(request):
    products = Product.objects.all().order_by('title')
    return render(request, 'dashboard/inventory_list.html', {
        'products': products,
        'low_stock_threshold': LOW_STOCK_THRESHOLD,
    })


@staff_member_required
def product_create(request):
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product added.')
            return redirect('dashboard_inventory')
    else:
        form = ProductForm()
    return render(request, 'dashboard/product_form.html', {'form': form, 'title': 'Add product'})


@staff_member_required
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        form = ProductForm(request.POST, request.FILES, instance=product)
        if form.is_valid():
            form.save()
            messages.success(request, 'Product updated.')
            return redirect('dashboard_inventory')
    else:
        form = ProductForm(instance=product)
    return render(request, 'dashboard/product_form.html', {'form': form, 'title': f'Edit: {product.title}'})


@staff_member_required
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        messages.success(request, 'Product deleted.')
        return redirect('dashboard_inventory')
    return render(request, 'dashboard/product_confirm_delete.html', {'product': product})


def _parse_date(value):
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None


def _report_orders(request):
    """Paid orders filtered by optional ?start= / ?end= date strings (YYYY-MM-DD)."""
    orders = Order.objects.filter(status='paid')
    start = _parse_date(request.GET.get('start'))
    end = _parse_date(request.GET.get('end'))
    if start:
        orders = orders.filter(created_at__date__gte=start)
    if end:
        orders = orders.filter(created_at__date__lte=end)
    return orders, start, end


@staff_member_required
def reports(request):
    orders, start, end = _report_orders(request)

    units_sold = (
        OrderItem.objects.filter(order__in=orders).aggregate(total=Sum('quantity'))['total'] or 0
    )

    top_products = (
        OrderItem.objects.filter(order__in=orders)
        .values('product_title')
        .annotate(
            qty=Sum('quantity'),
            revenue=Sum(F('product_price') * F('quantity')),
        )
        .order_by('-revenue')[:10]
    )

    daily = (
        orders.annotate(day=TruncDate('created_at'))
        .values('day')
        .annotate(revenue=Sum('total_price'), orders=Count('id'))
        .order_by('-day')
    )

    context = {
        'total_revenue': orders.aggregate(total=Sum('total_price'))['total'] or 0,
        'order_count': orders.count(),
        'units_sold': units_sold,
        'top_products': top_products,
        'daily': daily,
        'start': request.GET.get('start', ''),
        'end': request.GET.get('end', ''),
    }
    return render(request, 'dashboard/reports.html', context)


@staff_member_required
def reports_export(request):
    orders, start, end = _report_orders(request)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="sales_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Order', 'Customer', 'Status', 'Total', 'Created'])
    for order in orders.select_related('user'):
        writer.writerow([
            order.order_number,
            order.user.username,
            order.status,
            order.total_price,
            order.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    return response
