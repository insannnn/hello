from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout

# Create your views here.
def home(request):
    return render(request, 'authentication/index.html')

def signup(request):
    if request.method == 'POST':
        username = request.POST['username']
        fname = request.POST['fname']
        lname = request.POST['lname']  
        email = request.POST['email'] 
        password1 = request.POST['password1'] 
        password2 = request.POST['password2']    

        myuser = User.objects.create_user(username, email, password1)
        myuser.first_name = fname
        myuser.last_name = lname
        myuser.save()

        return redirect('signin')
    
    # Handle GET request (show the signup form)
    return render(request, 'authentication/signup.html')


def signin(request):
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']

        user = authenticate(username=username, password=password)

        if user is not None:
            login(request, user)
            fname = user.first_name
            return render(request, 'authentication/dashboard.html', {'fname': fname})
        else:
            messages.error(request, "Invalid username or password.")
            return render(request, 'authentication/signin.html')

    return render(request, 'authentication/signin.html')

def signout(request):
    logout (request)
    messages.success(request, 'Logged out succesfully!')
    return redirect('home')

def dashboard(request):
    return render(request, 'authentication/dashboard.html')