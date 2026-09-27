from application.tenancy import filtrar_por_loja
from infrastructure.models import RegistroDeAlteracao


def registros_do_usuario(user, acao=''):
    registros = filtrar_por_loja(RegistroDeAlteracao.objects.select_related('usuario'), user)
    if acao:
        registros = registros.filter(acao=acao)
    return registros.order_by('-data', '-pk')
