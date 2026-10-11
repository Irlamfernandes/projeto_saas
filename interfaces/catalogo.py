"""Lista de produtos que a busca da tela de venda usa no navegador (vai para a página via json_script)."""
from collections import Counter


def catalogo_para_venda(produtos, venda=None):
    """`venda`: a venda em edição. O que ela já prendeu do estoque volta a ficar disponível para ela.

    `estoque` None = produto sem controle de estoque (vende qualquer quantidade). `casas`: decimais aceitos.
    """
    por_produto, por_variacao = Counter(), Counter()
    for item in venda.itens.all() if venda else ():
        por_produto[item.produto_id] += item.quantidade
        por_variacao[item.variacao_id] += item.quantidade
    return [
        {
            'id': produto.pk,
            'nome': produto.nome,
            'codigo': produto.codigo_interno,
            'preco': str(produto.preco_venda),
            'estoque': _estoque(produto, produto.quantidade_estoque + por_produto[produto.pk]),
            'unidade': produto.sigla,
            'casas': produto.casas_decimais,
            'variacoes': [
                {
                    'id': variacao.pk, 'nome': variacao.nome, 'acrescimo': str(variacao.acrescimo),
                    'estoque': _estoque(produto, variacao.quantidade_estoque + por_variacao[variacao.pk]),
                }
                for variacao in produto.variacoes.all()
            ],
        }
        for produto in produtos.prefetch_related('variacoes')
    ]


def _estoque(produto, quantidade):
    return float(quantidade) if produto.controla_estoque else None


def itens_da_venda(venda):
    """Itens atuais da venda no formato do carrinho, com o preço e a variação da época."""
    return [
        {
            'id': item.produto_id, 'quantidade': float(item.quantidade), 'preco': str(item.preco_unitario),
            'variacao': item.variacao_id,
        }
        for item in venda.itens.all()
    ]
