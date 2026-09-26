from functools import wraps
from django.contrib.auth.decorators import login_required
from application.tenancy import verificar_acesso_loja


def loja_required(view):
    """Exige login e acesso a uma loja ativa antes de executar a view."""
    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        verificar_acesso_loja(request.user)
        return view(request, *args, **kwargs)
    return wrapper
