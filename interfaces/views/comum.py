from django.contrib import messages
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
