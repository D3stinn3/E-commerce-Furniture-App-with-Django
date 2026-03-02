from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from .models import *
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger

def store(request):
    products = Product.objects.all()
    paginator = Paginator(products, 6)
    page_number = request.GET.get('page')
    try:
        paginated_products = paginator.page(page_number)
    except PageNotAnInteger:
        paginated_products = paginator.page(1)
    except EmptyPage:
        paginated_products = paginator.page(paginator.num_pages)
    return render(request, 'store.html', {'products': paginated_products})

def load_more_products(request):
    offset = int(request.GET.get('offset', 0))
    limit = int(request.GET.get('limit', 2))
    products = Product.objects.all()[offset:offset+limit]
    products_data = [{'name': product.name} for product in products]
    return JsonResponse({'products': products_data})

def product_list(request):
    products = Product.objects.all()

    # Filter products based on user-selected criteria
    category = request.GET.get('category')
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    filter_offer = request.GET.get('offer', None)
    
    if filter_offer == 'true':
        products = products.filter(offer=True)
    if category:
        products = products.filter(category__icontains=category)
    if min_price:
        products = products.filter(price__gte=min_price)
    if max_price:
        products = products.filter(price__lte=max_price)

    return render(request, 'product.html', {'products': products, 'category':category, 'min_price':min_price, 'max_price':max_price})

def search(request):
    query = request.GET.get('query')
    products = Product.objects.all()
    pcq = products.filter(category__icontains=query)
    ptq = products.filter(title__icontains=query)
    return render(request, 'search.html', {'products': pcq, 'products': ptq, 'navbar': '#search', 'query': query})

def view_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'cart.html', {'cart_items': cart_items, 'total_price': total_price})
 
@login_required
def add(request, product_id):
    product = Product.objects.get(id=product_id)
    cart_item, created = CartItem.objects.get_or_create(product=product, 
                                                       user=request.user)
    cart_item.quantity += 1
    cart_item.save()
    return redirect('view_cart')

def remove(request, item_id):
    cart_item = CartItem.objects.get(id=item_id)
    cart_item.delete()
    return redirect('view_cart')


@login_required
@require_POST
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')

    if not cart_items.exists():
        return redirect('view_cart')

    total_price = sum(item.product.price * item.quantity for item in cart_items)

    order = Order.objects.create(
        user=request.user,
        total_price=total_price,
    )

    order_items_to_create = []
    for item in cart_items:
        order_items_to_create.append(OrderItem(
            order=order,
            product_title=item.product.title,
            product_price=item.product.price,
            quantity=item.quantity,
        ))
    OrderItem.objects.bulk_create(order_items_to_create)

    cart_items.delete()

    return redirect('order_success', order_id=order.id)


@login_required
def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)
    return render(request, 'order_success.html', {'order': order})


@login_required
def download_receipt(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user)

    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT
    import io

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            topMargin=30*mm, bottomMargin=20*mm,
                            leftMargin=20*mm, rightMargin=20*mm)

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#037bc0'),
        spaceAfter=6,
    )
    subtitle_style = ParagraphStyle(
        'ReceiptSubtitle',
        parent=styles['Normal'],
        fontSize=10,
        textColor=colors.HexColor('#333333'),
        alignment=TA_CENTER,
        spaceAfter=20,
    )
    heading_style = ParagraphStyle(
        'ReceiptHeading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#005485'),
        spaceAfter=10,
    )

    elements = []

    elements.append(Paragraph('Modern Furniture Store', title_style))
    elements.append(Paragraph('Thank you for your purchase!', subtitle_style))
    elements.append(Spacer(1, 10))

    elements.append(Paragraph('Order Details', heading_style))
    info_data = [
        ['Order Number:', order.order_number],
        ['Date:', order.created_at.strftime('%B %d, %Y at %I:%M %p')],
        ['Customer:', order.user.get_full_name() or order.user.username],
        ['Email:', order.user.email or 'N/A'],
    ]
    info_table = Table(info_data, colWidths=[120, 350])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 20))

    elements.append(Paragraph('Items Purchased', heading_style))
    table_data = [['Item', 'Qty', 'Unit Price', 'Total']]
    for item in order.items.all():
        table_data.append([
            item.product_title,
            str(item.quantity),
            f'${item.product_price}',
            f'${item.line_total}',
        ])
    table_data.append(['', '', 'Grand Total:', f'${order.total_price}'])

    items_table = Table(table_data, colWidths=[250, 50, 90, 90])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#037bc0')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        ('FONTNAME', (0, 1), (-1, -2), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -2), 10),
        ('BOTTOMPADDING', (0, 1), (-1, -2), 8),
        ('TOPPADDING', (0, 1), (-1, -2), 8),
        ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#f0f0f0')]),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TOPPADDING', (0, -1), (-1, -1), 12),
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#037bc0')),
        ('GRID', (0, 0), (-1, -2), 0.5, colors.HexColor('#cccccc')),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('ALIGN', (-1, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (-2, -1), (-2, -1), 'RIGHT'),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 30))

    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.HexColor('#888888'),
        alignment=TA_CENTER,
    )
    elements.append(Paragraph('This is a simulated purchase receipt.', footer_style))
    elements.append(Paragraph('Modern Furniture Store - All rights reserved', footer_style))

    doc.build(elements)

    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="receipt_{order.order_number}.pdf"'
    return response