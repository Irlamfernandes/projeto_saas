from infrastructure.models import Cobranca, Plano, StatusDaCobranca


def planos_disponiveis():
    return Plano.objects.filter(ativo=True)


def cobrancas_da_loja(loja):
    return Cobranca.objects.filter(loja=loja)


def em_teste_gratis(loja):
    """Loja que ainda não teve nenhum pagamento confirmado está no período grátis."""
    return not cobrancas_da_loja(loja).filter(status=StatusDaCobranca.PAGA).exists()
