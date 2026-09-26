from decimal import Decimal
from django.db import transaction
from django.db.models import F
from application.vendas.exceptions import EstoqueInsuficiente, ProdutoNaoEncontrado
from application.vendas.selectors import buscar_produto
from infrastructure.models import ItemVenda, PagamentoCliente, Produto, Venda


@transaction.atomic
def registrar_venda(*, cliente, termo_produto, quantidade, valor_pago=Decimal('0'), observacoes=''):
    """Cria a venda na loja do cliente, baixa o estoque e registra o pagamento feito no ato."""
    produto = _reservar_estoque(cliente.loja, termo_produto, quantidade)
    venda = Venda.objects.create(
        loja=cliente.loja,
        cliente=cliente,
        valor_total=produto.preco_venda * quantidade,
        observacoes=observacoes,
    )
    _salvar_item(ItemVenda(venda=venda), produto, quantidade)
    _registrar_pagamento_no_ato(venda, valor_pago)
    return venda


@transaction.atomic
def editar_venda(venda, *, cliente, termo_produto, quantidade, observacoes=''):
    """Substitui produto, quantidade e cliente da venda, devolvendo ao estoque o item anterior."""
    item = venda.itens.first()
    if item:
        _devolver_estoque(item)

    produto = _reservar_estoque(venda.loja, termo_produto, quantidade)
    venda.cliente = cliente
    venda.valor_total = produto.preco_venda * quantidade
    venda.observacoes = observacoes
    venda.save()
    _salvar_item(item or ItemVenda(venda=venda), produto, quantidade)
    return venda


def _reservar_estoque(loja, termo_produto, quantidade):
    encontrado = buscar_produto(loja, termo_produto)
    if encontrado is None:
        raise ProdutoNaoEncontrado(termo_produto)

    produto = Produto.objects.select_for_update().get(pk=encontrado.pk)
    if produto.quantidade_estoque < quantidade:
        raise EstoqueInsuficiente(produto)

    produto.quantidade_estoque -= quantidade
    produto.save(update_fields=['quantidade_estoque'])
    return produto


def _devolver_estoque(item):
    Produto.objects.filter(pk=item.produto_id).update(
        quantidade_estoque=F('quantidade_estoque') + item.quantidade
    )


def _salvar_item(item, produto, quantidade):
    item.produto = produto
    item.quantidade = quantidade
    item.preco_unitario = produto.preco_venda
    item.save()


def _registrar_pagamento_no_ato(venda, valor):
    if not valor:
        return
    PagamentoCliente.objects.create(
        loja=venda.loja,
        cliente=venda.cliente,
        valor=valor,
        observacao=f"Pagamento no ato da Venda #{venda.pk}",
    )
