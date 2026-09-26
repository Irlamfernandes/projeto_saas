from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from django.utils.http import url_has_allowed_host_and_scheme
from application.tenancy import loja_desativada
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


def _autenticar(request, form):
    """Retorna o usuário autorizado a entrar ou registra no form o motivo da recusa."""
    user = authenticate(
        request,
        username=form.cleaned_data['username'],
        password=form.cleaned_data['password'],
    )
    if user is None:
        form.add_error(None, 'Usuário ou senha inválidos.')
        return None
    if loja_desativada(user):
        form.add_error(None, 'Esta loja está desativada. Procure o administrador.')
        return None
    return user


def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.user.is_authenticated:
        return _redirecionar_usuario_autenticado(request.user, next_url, request)

    form = LoginForm(request.POST) if request.method == 'POST' else LoginForm()

    if form.is_bound and form.is_valid():
        user = _autenticar(request, form)
        if user is not None:
            login(request, user)
            return _redirecionar_usuario_autenticado(user, next_url, request)

    return render(request, TEMPLATE_LOGIN, {'form': form, 'next': next_url or ''})