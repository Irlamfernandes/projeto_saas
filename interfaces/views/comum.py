from django.contrib import messages
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from application.exceptions import RegraDeNegocioError


def executar_formulario(request, form, acao, mensagem_sucesso):
    """Valida o form, executa a ação de negócio e reporta o resultado via messages.

    Retorna True quando a ação foi concluída com sucesso.
    """
    if not form.is_valid():
        messages.error(request, primeiro_erro(form))
        return False

    try:
        acao()
    except RegraDeNegocioError as erro:
        messages.error(request, str(erro))
        return False

    messages.success(request, mensagem_sucesso)
    return True


def primeiro_erro(form):
    return next(iter(form.errors.values()))[0]


def redirecionar_apos_login(request, user, next_url=None):
    """Troca de senha pendente > `next` seguro > admin (equipe) > dashboard."""
    if user.deve_trocar_senha:
        return redirect('alterar_senha')
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
    ):
        return redirect(next_url)
    if user.is_superuser or user.is_staff:
        return redirect('/admin/')
    return redirect('dashboard')
