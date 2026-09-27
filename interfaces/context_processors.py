from application.assinatura.situacao import situacao_do_plano
from infrastructure.models import Tema
from interfaces.desenvolvedor import CORSARIOS_CODE


def plano(request):
    """Situação do plano da loja para os avisos do topo e do Início (None fora de uma loja)."""
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated or usuario.is_superuser:
        return {'plano': None}
    return {'plano': situacao_do_plano(usuario.loja)}


def desenvolvedor(_request):
    """Marca de quem fez o sistema, para o rodapé, o login e o suporte."""
    return {'desenvolvedor': CORSARIOS_CODE}


def tema(request):
    """Aparência da página: a escolhida pelo usuário; fora da conta (login), segue o aparelho."""
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated:
        return {'tema': Tema.AUTOMATICO}
    return {'tema': usuario.tema}
