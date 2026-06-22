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


@staff_member_required
def reports_export_pdf(request):
    orders, start, end = _report_orders(request)

    total_revenue = orders.aggregate(total=Sum('total_price'))['total'] or 0
    order_count = orders.count()
    units_sold = (
        OrderItem.objects.filter(order__in=orders).aggregate(total=Sum('quantity'))['total'] or 0
    )
    top_products = (
        OrderItem.objects.filter(order__in=orders)
        .values('product_title')
        .annotate(qty=Sum('quantity'), revenue=Sum(F('product_price') * F('quantity')))
        .order_by('-revenue')[:10]
    )

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=25 * mm, bottomMargin=20 * mm,
                            leftMargin=18 * mm, rightMargin=18 * mm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('RT', parent=styles['Title'], fontSize=20,
                                 textColor=colors.HexColor('#0f766e'), spaceAfter=4)
    sub_style = ParagraphStyle('RS', parent=styles['Normal'], fontSize=10,
                               textColor=colors.HexColor('#555555'), spaceAfter=16)
    heading_style = ParagraphStyle('RH', parent=styles['Heading2'], fontSize=13,
                                   textColor=colors.HexColor('#134e4a'), spaceAfter=8)

    period = 'All time'
    if start or end:
        period = f"{start or '…'} to {end or '…'}"

    elements = [
        Paragraph('Sales Report', title_style),
        Paragraph(f'Modern Furniture Store &mdash; {period}', sub_style),
    ]

    header_style = TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f3f4f6')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
    ])

    # Summary
    elements.append(Paragraph('Summary', heading_style))
    summary = Table([
        ['Metric', 'Value'],
        ['Revenue (paid)', f'KES {total_revenue}'],
        ['Paid orders', str(order_count)],
        ['Units sold', str(units_sold)],
    ], colWidths=[320, 140])
    summary.setStyle(header_style)
    elements.append(summary)
    elements.append(Spacer(1, 16))

    # Top products
    elements.append(Paragraph('Top products', heading_style))
    tp_data = [['Product', 'Qty', 'Revenue']]
    for row in top_products:
        tp_data.append([row['product_title'], str(row['qty']), f"KES {row['revenue']}"])
    if len(tp_data) == 1:
        tp_data.append(['No sales in this period.', '', ''])
    tp = Table(tp_data, colWidths=[300, 80, 80])
    tp.setStyle(header_style)
    elements.append(tp)
    elements.append(Spacer(1, 16))

    # Orders
    elements.append(Paragraph('Orders', heading_style))
    o_data = [['Order', 'Customer', 'Status', 'Total', 'Created']]
    for order in orders.select_related('user'):
        o_data.append([
            order.order_number,
            order.user.username,
            order.status,
            f'KES {order.total_price}',
            order.created_at.strftime('%Y-%m-%d %H:%M'),
        ])
    if len(o_data) == 1:
        o_data.append(['No orders in this period.', '', '', '', ''])
    od = Table(o_data, colWidths=[80, 130, 70, 90, 110])
    od.setStyle(header_style)
    elements.append(od)

    doc.build(elements)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="sales_report.pdf"'
    return response
