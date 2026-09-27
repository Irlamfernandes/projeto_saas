from functools import partial, wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from application.assinatura.situacao import plano_vencido
from application.tenancy import verificar_acesso_loja

AVISO_PLANO_VENCIDO = (
    "Seu plano venceu e nada foi salvo. Renove em Configurações para voltar a registrar vendas e fazer alterações."
)


def loja_required(view=None, *, trava_plano_vencido=True):
    """Exige login, acesso a uma loja ativa e que a senha temporária já tenha sido trocada.

    Com o plano vencido a loja só consulta: envios de formulário voltam com um aviso. Telas que precisam
    funcionar mesmo assim (renovar o plano, por exemplo) usam `trava_plano_vencido=False`.
    """
    if view is None:
        return partial(loja_required, trava_plano_vencido=trava_plano_vencido)

    @login_required
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        verificar_acesso_loja(request.user)
        if request.user.deve_trocar_senha:
            return redirect('alterar_senha')
        if trava_plano_vencido and request.method == 'POST' and plano_vencido(request.user):
            messages.warning(request, AVISO_PLANO_VENCIDO)
            return _voltar(request)
        return view(request, *args, **kwargs)
    return wrapper


def _voltar(request):
    """Volta para a tela de onde veio o envio (se for deste site); senão, para o Início."""
    anterior = request.META.get('HTTP_REFERER')
    if anterior and url_has_allowed_host_and_scheme(anterior, allowed_hosts={request.get_host()}):
        return redirect(anterior)
    return redirect('dashboard')
