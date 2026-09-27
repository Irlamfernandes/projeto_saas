"""Lista de produtos que a busca da tela de venda usa no navegador (vai para a página via json_script)."""


def catalogo_para_venda(produtos, reservados=None):
    """`reservados`: {id do produto: quantidade} já presa na venda em edição — volta a ficar disponível para ela."""
    reservados = reservados or {}
    return [
        {
            'id': produto.pk,
            'nome': produto.nome,
            'codigo': produto.codigo_interno,
            'preco': str(produto.preco_venda),
            'estoque': produto.quantidade_estoque + reservados.get(produto.pk, 0),
        }
        for produto in produtos
    ]


def itens_da_venda(venda):
    """Itens atuais da venda no formato do carrinho, com o preço da época."""
    return [
        {'id': item.produto_id, 'quantidade': item.quantidade, 'preco': str(item.preco_unitario)}
        for item in venda.itens.all()
    ]
