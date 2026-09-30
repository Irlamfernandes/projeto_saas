from django.db.models import Q
from application.tenancy import filtrar_por_loja
from infrastructure.models import Produto

ORDEM_PADRAO = '-data_criacao'
ORDENACOES_PERMITIDAS = frozenset({
    'nome', '-nome',
    'preco_venda', '-preco_venda',
    'quantidade_estoque', '-quantidade_estoque',
    'data_criacao', ORDEM_PADRAO,
})
LIMITE_ESTOQUE_BAIXO = 5
MAXIMO_DE_FOTOS = 5


def produtos_do_usuario(user):
    return filtrar_por_loja(Produto.objects.all(), user)


def filtrar_produtos(produtos, *, busca='', categoria='', baixo_estoque=False, ordem=ORDEM_PADRAO):
    if busca:
        produtos = produtos.filter(Q(nome__icontains=busca) | Q(codigo_interno__icontains=busca))
    if categoria:
        produtos = produtos.filter(categoria=categoria)
    if baixo_estoque:
        produtos = produtos.filter(controla_estoque=True, quantidade_estoque__lte=LIMITE_ESTOQUE_BAIXO)
    return produtos.prefetch_related('imagens').order_by(ordem)


def categorias_em_uso(produtos):
    return list(
        produtos.exclude(categoria='')
        .order_by('categoria')
        .values_list('categoria', flat=True)
        .distinct()
    )


def fotos_disponiveis(produto):
    """Quantas fotos ainda cabem no produto."""
    return max(0, MAXIMO_DE_FOTOS - produto.imagens.count())
