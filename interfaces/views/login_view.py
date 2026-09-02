from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from interfaces.forms.login_form import LoginForm

def login_view(request):
    if request.user.is_authenticated:
        if request.user.is_superuser or request.user.is_staff:
            return redirect('/admin/')
        if request.user.deve_trocar_senha:
            return redirect('alterar_senha')
        return redirect('dashboard')

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                
                # Se for da equipe/admin, manda direto para a URL raiz do admin
                if user.is_superuser or user.is_staff:
                    return redirect('/admin/')
                
                if user.deve_trocar_senha:
                    return redirect('alterar_senha')
                    
                return redirect('dashboard')
            else:
                form.add_error(None, 'Usuário ou senha inválidos.')
    else:
        form = LoginForm()

    return render(request, 'interfaces/login.html', {'form': form})