"""Lista de produtos que a busca da tela de venda usa no navegador (vai para a página via json_script)."""
from application.vendas.opcoes import escolhas_do_item


def catalogo_para_venda(produtos, reservados=None):
    """`reservados`: {id do produto: quantidade} já presa na venda em edição — volta a ficar disponível para ela.

    `estoque` None = produto sem controle de estoque (vende qualquer quantidade). `casas`: decimais aceitos.
    """
    reservados = reservados or {}
    return [
        {
            'id': produto.pk,
            'nome': produto.nome,
            'codigo': produto.codigo_interno,
            'preco': str(produto.preco_venda),
            'estoque': _estoque(produto, reservados.get(produto.pk, 0)),
            'unidade': produto.sigla,
            'casas': produto.casas_decimais,
            'opcoes': produto.opcoes,
        }
        for produto in produtos
    ]


def _estoque(produto, reservado):
    if not produto.controla_estoque:
        return None
    return float(produto.quantidade_estoque + reservado)


def itens_da_venda(venda):
    """Itens atuais da venda no formato do carrinho, com o preço e as opções escolhidas na época."""
    return [
        {
            'id': item.produto_id, 'quantidade': float(item.quantidade), 'preco': str(item.preco_unitario),
            'opcoes': escolhas_do_item(item.opcoes),
        }
        for item in venda.itens.all()
    ]
