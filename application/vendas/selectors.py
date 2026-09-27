from django.db.models import Q
from application.tenancy import filtrar_por_loja
from infrastructure.models import Produto, Venda


def vendas_do_usuario(user):
    vendas = Venda.objects.select_related('cliente').prefetch_related('itens__produto', 'parcelas')
    return filtrar_por_loja(vendas, user).order_by('-data_venda')


def produtos_em_estoque_do_usuario(user):
    """O que dá para vender agora: com estoque, ou sem controle de estoque."""
    return filtrar_por_loja(Produto.objects.filter(Q(controla_estoque=False) | Q(quantidade_estoque__gt=0)), user)


def produtos_da_loja(loja):
    return Produto.objects.filter(loja=loja)
