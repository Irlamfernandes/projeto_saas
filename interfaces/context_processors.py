from application.assinatura.situacao import situacao_do_plano


def plano(request):
    """Situação do plano da loja para os avisos do topo e do Início (None fora de uma loja)."""
    usuario = getattr(request, 'user', None)
    if usuario is None or not usuario.is_authenticated or usuario.is_superuser:
        return {'plano': None}
    return {'plano': situacao_do_plano(usuario.loja)}
