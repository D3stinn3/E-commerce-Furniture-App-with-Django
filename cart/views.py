import uuid

import requests
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.urls import reverse
from django.conf import settings
from django.contrib import messages
from django.db.models import Q, F, Value
from django.db.models.functions import Greatest
from .models import *
from . import paystack
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
    products_data = [
        {
            'id': product.id,
            'title': product.title,
            'price': product.price,
            'img': product.img.url if product.img else '',
        }
        for product in products
    ]
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
    query = request.GET.get('query') or ''
    products = Product.objects.all()
    if query:
        products = products.filter(
            Q(title__icontains=query) | Q(category__icontains=query)
        )
    return render(request, 'search.html', {'products': products, 'navbar': '#search', 'query': query})

@login_required
def view_cart(request):
    cart_items = CartItem.objects.filter(user=request.user)
    total_price = sum(item.product.price * item.quantity for item in cart_items)
    return render(request, 'cart.html', {'cart_items': cart_items, 'total_price': total_price})

@login_required
def add(request, product_id):
    product = get_object_or_404(Product, id=product_id)
    cart_item, created = CartItem.objects.get_or_create(product=product,
                                                       user=request.user)
    cart_item.quantity += 1
    cart_item.save()
    return redirect('view_cart')

@login_required
def remove(request, item_id):
    cart_item = get_object_or_404(CartItem, id=item_id, user=request.user)
    cart_item.delete()
    return redirect('view_cart')


@login_required
@require_POST
def checkout(request):
    cart_items = CartItem.objects.filter(user=request.user).select_related('product')

    if not cart_items.exists():
        return redirect('view_cart')

    if not request.user.email:
        messages.error(request, 'Please add an email address to your account before paying.')
        return redirect('view_cart')

    total_price = sum(item.product.price * item.quantity for item in cart_items)

    # Create a pending order and snapshot the items. The cart is NOT cleared yet;
    # it is only cleared once Paystack confirms the payment in paystack_callback.
    order = Order.objects.create(
        user=request.user,
        total_price=total_price,
        status='pending',
    )

    order_items_to_create = [
        OrderItem(
            order=order,
            product_title=item.product.title,
            product_price=item.product.price,
            quantity=item.quantity,
        )
        for item in cart_items
    ]
    OrderItem.objects.bulk_create(order_items_to_create)

    reference = f'{order.id}-{uuid.uuid4().hex[:8]}'
    order.paystack_reference = reference
    order.save(update_fields=['paystack_reference'])

    # Build the callback from the current request so Paystack returns the buyer to
    # the exact same host (scheme + hostname) they are browsing on. This keeps the
    # session cookie valid (127.0.0.1 and localhost are separate cookie jars).
    callback_url = request.build_absolute_uri(reverse('paystack_callback'))

    try:
        data = paystack.initialize_transaction(
            email=request.user.email,
            amount_subunit=total_price * 100,  # KES -> cents
            reference=reference,
            callback_url=callback_url,
        )
    except (requests.RequestException, ValueError) as exc:
        order.status = 'failed'
        order.save(update_fields=['status'])
        messages.error(request, f'Could not start payment: {exc}')
        return redirect('view_cart')

    return redirect(data['authorization_url'])


def paystack_callback(request):
    # No @login_required: Paystack's verification (not the browser session) is the
    # source of truth here. The order is finalized only when Paystack confirms the
    # reference was paid, so this is safe even for an anonymous/third-party hit.
    reference = request.GET.get('reference') or request.GET.get('trxref')
    if not reference:
        messages.error(request, 'Missing payment reference.')
        return redirect('view_cart')

    order = get_object_or_404(Order, paystack_reference=reference)

    # Already finalized – just show the result.
    if order.status == 'paid':
        return redirect(_order_success_url(order))

    try:
        data = paystack.verify_transaction(reference)
    except (requests.RequestException, ValueError) as exc:
        messages.error(request, f'Could not verify payment: {exc}')
        return redirect('view_cart')

    if data.get('status') == 'success':
        order.status = 'paid'
        order.save(update_fields=['status'])

        # Decrement stock for purchased products (match by title snapshot).
        for item in order.items.all():
            Product.objects.filter(title=item.product_title).update(
                stock=Greatest(F('stock') - item.quantity, Value(0))
            )

        # Clear the buyer's cart (the order owner, not necessarily request.user).
        CartItem.objects.filter(user=order.user).delete()
        return redirect(_order_success_url(order))

    order.status = 'failed'
    order.save(update_fields=['status'])
    messages.error(request, 'Payment was not completed. Your cart has been kept.')
    return redirect('view_cart')


def _order_success_url(order):
    """Order-success URL including the reference token so the receipt is viewable
    even if the session is momentarily absent (e.g. returning from Paystack)."""
    return f"{reverse('order_success', args=[order.id])}?ref={order.paystack_reference}"


def order_success(request, order_id):
    order = get_object_or_404(Order, id=order_id)
    # Grant access to the owner, or to anyone presenting the matching reference
    # token (used right after the Paystack redirect, before the session settles).
    ref = request.GET.get('ref')
    is_owner = request.user.is_authenticated and order.user_id == request.user.id
    if not is_owner and (not ref or ref != order.paystack_reference):
        return redirect('login')
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

    # Brand colors mirror static/css/theme.css (--color-primary / --color-primary-dark);
    # ReportLab can't read CSS vars, so keep these hexes in sync with the theme.
    title_style = ParagraphStyle(
        'ReceiptTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#0f766e'),
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
        textColor=colors.HexColor('#134e4a'),
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
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#0f766e')),
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
        ('LINEABOVE', (0, -1), (-1, -1), 2, colors.HexColor('#0f766e')),
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