from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User, auth

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
                # Create a ready-to-use account (no email confirmation step).
                User.objects.create_user(username=username, password=password1, email=email)

                messages.success(request, 'Account created. You can now log in.')
                return redirect('login')
        else:
            messages.info(request,'Password not matching..')
            return redirect('signup')
    else:
        return render(request,'signup.html')

def logout (request):
    auth.logout(request)
    return redirect('/')
