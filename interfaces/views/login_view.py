from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.utils.http import url_has_allowed_host_and_scheme
from interfaces.forms.login_form import LoginForm

def login_view(request):
    if request.user.is_authenticated:
        if request.user.deve_trocar_senha:
            return redirect('alterar_senha')
        if request.user.is_superuser or request.user.is_staff:
            return redirect('/admin/')
        return redirect('dashboard')

    next_url = request.GET.get('next') or request.POST.get('next')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                
                if user.deve_trocar_senha:
                    return redirect('alterar_senha')
                    
                if next_url and url_has_allowed_host_and_scheme(
                    next_url, 
                    allowed_hosts={request.get_host()}, 
                    require_https=request.is_secure()
                ):
                    return redirect(next_url)

                if user.is_superuser or user.is_staff:
                    return redirect('/admin/')
                    
                return redirect('dashboard')
            else:
                form.add_error(None, 'Usuário ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'interfaces/login.html', {'form': form, 'next': next_url or ''})