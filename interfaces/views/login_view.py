from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.utils.http import url_has_allowed_host_and_scheme
from interfaces.forms.login_form import LoginForm

TEMPLATE_LOGIN = 'interfaces/login.html'


def _redirecionar_usuario_autenticado(user, next_url, request):
    """Determina para onde o usuário autenticado deve ser redirecionado."""
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


def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.user.is_authenticated:
        return _redirecionar_usuario_autenticado(request.user, next_url, request)

    form = LoginForm()

    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            
            user = authenticate(request, username=username, password=password)
            if user is not None:
                login(request, user)
                return _redirecionar_usuario_autenticado(user, next_url, request)
            
            form.add_error(None, 'Usuário ou senha inválidos.')

    return render(request, TEMPLATE_LOGIN, {'form': form, 'next': next_url or ''})