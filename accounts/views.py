from django.shortcuts import render, redirect
from django.contrib.auth import login
from .forms import UserCreateForm  

def register(request):
    if request.method == 'POST':
        form = UserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)  
            return redirect('login') 
    else:
        form = UserCreateForm()

    return render(request, 'accounts/register.html', {'form': form})