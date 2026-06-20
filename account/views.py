from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User, auth
from django.conf import settings
from django.core.mail import send_mail
from django.urls import reverse
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

# Create your views here.
# ACCOUNT

def login(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = auth.authenticate(username=username,password=password)
        
        if user is not None:
            auth.login(request, user)
            return redirect('/')
        else:
            messages.info(request,'Invalid Credentials')
            return redirect('login')

    else:
        return render(request,'login.html')
 
def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        password1 = request.POST['password1']
        password2 = request.POST['password2']
        email = request.POST['email']

        if password1==password2:
            if User.objects.filter(username=username).exists():
                messages.info(request,'Username taken')
                return redirect('signup')
            elif User.objects.filter(email=email).exists():
                messages.info(request,'Email taken')
                return redirect('signup')
            else:
                # Create the account inactive until the email link is confirmed.
                user = User.objects.create_user(username=username, password=password1, email=email)
                user.is_active = False
                user.save()

                # Send confirmation email with an activation link.
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                send_confirmation_email(request, username, email, uid, token)

                messages.success(request, 'Account created. Check your email to activate it before logging in.')
                return redirect('login')
        else:
            messages.info(request,'Password not matching..')
            return redirect('signup')
    else:
        return render(request,'signup.html')
    
def logout (request):
    auth.logout(request)
    return redirect('/')


def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        messages.success(request, 'Your account is now active. You can log in.')
    else:
        messages.error(request, 'Activation link is invalid or has expired.')
    return redirect('login')


def send_confirmation_email(request, username, email, uid, token):
    activation_path = reverse('activate', kwargs={'uidb64': uid, 'token': token})
    activation_url = settings.BASE_URL + activation_path
    subject = f'{username}, activate your Furniture Store account'
    message = (
        f'Hi {username},\n\nWelcome to Furniture Store. '
        f'Please activate your account by clicking the link below:\n\n{activation_url}\n\n'
        f'If you did not create this account, you can ignore this email.'
    )
    email_from = settings.EMAIL_HOST_USER
    recipient_list = [email]
    send_mail(subject, message, email_from, recipient_list)