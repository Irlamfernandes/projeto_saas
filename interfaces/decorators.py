from functools import wraps
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from application.tenancy import verificar_acesso_loja


def loja_required(view):
    """Exige login, acesso a uma loja ativa e que a senha temporária já tenha sido trocada."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        verificar_acesso_loja(request.user)
        if request.user.deve_trocar_senha:
            return redirect('alterar_senha')
        return view(request, *args, **kwargs)
    return wrapper
