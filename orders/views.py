from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from carts.models import Cart, CartItem
from store.models import Product
from .forms import OrderForm
from .models import Order, OrderProduct, Payment
import datetime
from .models import Order, Payment
import json




#Verification email
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes
from django.core.mail import EmailMessage
from django.contrib.auth.decorators import login_required
from django.contrib.auth.tokens import default_token_generator
from django.conf import settings
# Create your views here.



def payments(request):
    body = json.loads(request.body)

    order = Order.objects.get(user = request.user, is_ordered = False, order_number = body['orderID'])
    
    # Store transaction orderData inside Payment method
    payment = Payment(
        user = request.user,
        payment_id = body['transID'],
        payment_method = body['payment_method'],
        payment_paid = order.order_total,
        status = body['status'],
    )
    
    payment.save()
    order.payment = payment
    order.is_ordered = True
    order.save()
    
    
    cart_items = CartItem.objects.filter(user = request.user)
    
    
    for cart_item in cart_items:
        order_product = OrderProduct()
        order_product.order_id = order.id
        order_product.payment = payment
        order_product.user_id = request.user.id
        order_product.product_id = cart_item.product_id
        order_product.quantity = cart_item.quantity
        order_product.product_price = cart_item.product.price
        order_product.ordered = True
        order_product.save()

        item = CartItem.objects.get(id=cart_item.id)
        product_variation = item.variations.all()
        order_product = OrderProduct.objects.get(id=order_product.id)
        order_product.variations.set(product_variation)
        order_product.save()
        
        


        #Reduce quantity from product
        product = Product.objects.get(id = cart_item.product.id)
        product.stock -= cart_item.quantity
        product.save()
    
    # Delete cart 
    CartItem.objects.filter(user = request.user).delete()
    
    # Send order recieved email to customer
    
    mail_subject = 'Thanks you for order.'
    message = render_to_string('orders/order_recieved_email.html', {
        'user': request.user,
        'order': order,
    })
    email = request.user.email
    send_email = EmailMessage(
        subject= mail_subject,
        body= message,
        from_email= settings.EMAIL_FROM_USER,
        to=[email])
    send_email.send()
    
    data = {
        'order_number' : order.order_number,
        'transID' : payment.payment_id,
    }
    return JsonResponse(data)
    

def order_complete(request):
    order_number = request.GET.get('order_number')
    transID = request.GET.get('payment_id')
    
    try:
        order = Order.objects.get(order_number = order_number, is_ordered = True)
        order_products = OrderProduct.objects.filter(order__id = order.id)
        subtotal = 0
        for i in order_products:
            subtotal += i.product_price * i.quantity
        payment = Payment.objects.get(payment_id = transID)

        context = {
            'order': order,
            'order_number': order.order_number,
            'order_products': order_products,
            'transID': payment.payment_id,
            'payment': payment,
            'subtotal': subtotal,
            
        }
        return render(request, 'orders/order_complete.html', context)
    except (Payment.DoesNotExist , Order.DoesNotExist):
        return redirect('home')
        
def place_order(request, total =0, quantity = 0):
    current_user = request.user 
    
    cart_items = CartItem.objects.filter(user = current_user)
    cart_count = cart_items.count()
    if cart_count <=0:
        return redirect('store')
    
    
    grand_total = 0
    tax = 0
    
    for cart_item in cart_items:
        total += (cart_item.product.price * cart_item.quantity)  
        quantity += cart_item.quantity
    tax = (2 * total)/100
    grand_total = total + tax 
    
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            #store all the billing information inside Order table
            data = Order()
            data.user = current_user
            data.first_name = form.cleaned_data['first_name']
            data.last_name = form.cleaned_data['last_name']
            data.phone = form.cleaned_data['phone']
            data.email = form.cleaned_data['email']
            data.address_line_1 = form.cleaned_data['address_line_1']
            data.address_line_2 = form.cleaned_data['address_line_2']
            data.country = form.cleaned_data['country']
            data.state = form.cleaned_data['state']
            data.city = form.cleaned_data['city']
            data.order_note = form.cleaned_data['order_note']
            data.order_total = grand_total
            data.tax = tax
            data.ip = request.META.get('REMOTE_ADDR')
            data.save()
        
            # Generate order number
            yr = int(datetime.date.today().strftime('%Y'))
            dt = int(datetime.date.today().strftime('%d'))
            mt = int(datetime.date.today().strftime('%m'))
            d = datetime.date(yr, mt, dt)
            current_date = d.strftime("%Y%m%d")
            
            order_number = current_date + str(data.id)
            data.order_number = order_number
            
            data.save()
            
            order = Order.objects.get(user = current_user, is_ordered = False, order_number=order_number)
            
            context= {
                'order':order,
                'cart_items': cart_items,
                'tax': tax,
                'total': total,
                'grand_total': grand_total
            }
            return render(request, 'orders/payments.html', context)
    else:
        return redirect('checkout')
            
            