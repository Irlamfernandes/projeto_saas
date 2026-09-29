from django.contrib.auth import authenticate, login
from django.shortcuts import render
from application.contas.tentativas import minutos_bloqueado
from application.tenancy import loja_desativada
from interfaces.forms.login_form import LoginForm
from interfaces.views.comum import redirecionar_apos_login

TEMPLATE_LOGIN = 'interfaces/login.html'


def _autenticar(request, form):
    """Retorna o usuário autorizado a entrar ou registra no form o motivo da recusa."""
    user = authenticate(
        request,
        username=form.cleaned_data['username'],
        password=form.cleaned_data['password'],
    )
    if user is None:
        form.add_error(None, _motivo_da_recusa(form.cleaned_data['username']))
        return None
    if loja_desativada(user):
        form.add_error(None, 'Esta loja está desativada. Procure o administrador.')
        return None
    return user


def _motivo_da_recusa(usuario):
    minutos = minutos_bloqueado(usuario)
    if minutos:
        tempo = "1 minuto" if minutos == 1 else f"{minutos} minutos"
        return f"Muitas tentativas com senha errada. Por segurança, tente de novo daqui a {tempo}."
    return 'Usuário ou senha inválidos.'


def login_view(request):
    next_url = request.GET.get('next') or request.POST.get('next')

    if request.user.is_authenticated:
        return redirecionar_apos_login(request, request.user, next_url)

    form = LoginForm(request.POST) if request.method == 'POST' else LoginForm()

    if form.is_bound and form.is_valid():
        user = _autenticar(request, form)
        if user is not None:
            login(request, user)
            return redirecionar_apos_login(request, user, next_url)

    return render(request, TEMPLATE_LOGIN, {'form': form, 'next': next_url or ''})
