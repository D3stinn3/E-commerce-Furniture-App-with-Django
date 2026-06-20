from django.shortcuts import render, redirect
from django.conf import settings
from django.contrib import messages
from .models import *
from django.core.mail import EmailMessage
from .forms import ContactForm

# Create your views here.
def index(request):
    categorys = Category.objects.all()
    return render(request,'index.html', {'categorys':categorys})

def blog(request):
    blogs = Blog.objects.all()
    return render(request,'blog.html', {'blogs':blogs})

def blogentry(request, id):
    blogs = Blog.objects.all()
    blogs = Blog.objects.filter(id=id)
    return render(request,'blogentry.html', {'blogs':blogs})

def contact(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            phone_no = form.cleaned_data['phone_no']
            message = form.cleaned_data['message']
            # Gmail rejects an arbitrary "from", so send from the configured account
            # and set the visitor's address as reply-to instead.
            mail = EmailMessage(
                subject=subject,
                body=f'Name: {name}\nEmail: {email}\nPhone Number: {phone_no}\nMessage: {message}',
                from_email=settings.EMAIL_HOST_USER,
                to=[settings.EMAIL_RECEIVING_USER],
                reply_to=[email],
            )
            try:
                mail.send(fail_silently=False)
            except Exception:
                messages.error(request, 'Sorry, your message could not be sent. Please try again later.')
                return render(request, 'contact.html', {'form': form})
            return redirect('success')  # Redirect to a success page
    else:
        form = ContactForm()
    return render(request, 'contact.html', {'form': form})

def success(request):
    return render(request, 'success.html')

def gallery(request):
    gallerys = Gallery.objects.all()
    return render(request,'gallery.html', {'gallerys': gallerys})