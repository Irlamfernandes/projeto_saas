"""Compras (entram no estoque), despesas e perdas (saem do estoque), sempre com o histórico em dia.

Excluir desfaz o efeito no estoque. Produto sem controle de estoque não tem quantidade mexida.
"""
from collections import defaultdict
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from application.auditoria.services import registrar_alteracao
from application.gastos.exceptions import (
    CompraSemItens, EstoqueJaUsado, EstoqueNaoCobreAPerda, ProdutoDeOutraLoja, QuantidadeInvalidaParaUnidade,
)
from infrastructure.models import Acao, Compra, Despesa, ItemCompra, Perda, Produto
from infrastructure.models.produto import quantidade_aceita
from infrastructure.models.venda import subtotal
from infrastructure.utils.formatacao import item as descrever_item, quantidade as formatar_quantidade, reais


@transaction.atomic
def registrar_compra(*, loja, itens, data, fornecedor='', observacao='', atualizar_custo=True, usuario=None):
    """`itens`: trios (id do produto, quantidade, custo unitário). Soma no estoque e, se pedido, vira o novo custo."""
    if not itens:
        raise CompraSemItens()
    produtos = _travar_produtos(loja, {produto_id for produto_id, _, _ in itens})
    compra = Compra.objects.create(loja=loja, data=data, fornecedor=fornecedor, observacao=observacao, usuario=usuario)
    for produto_id, quantidade, custo in itens:
        produto = produtos[produto_id]
        _conferir_quantidade(produto, quantidade)
        ItemCompra.objects.create(compra=compra, produto=produto, quantidade=quantidade, custo_unitario=custo)
        _mexer_no_estoque(produto, quantidade)
        if atualizar_custo:
            Produto.objects.filter(pk=produto.pk).update(preco_custo=custo)
    compra.valor_total = sum((subtotal(q, custo) for _, q, custo in itens), Decimal('0'))
    compra.save(update_fields=['valor_total'])
    registrar_alteracao(
        loja=loja, usuario=usuario, acao=Acao.COMPRA_REGISTRADA,
        descricao=f"Compra #{compra.pk}{_de(fornecedor)} · {reais(compra.valor_total)}",
        detalhes={'itens': _descrever_itens(compra)},
    )
    return compra


@transaction.atomic
def excluir_compra(compra, *, usuario=None):
    """Tira do estoque o que a compra tinha colocado (se ainda estiver lá). O custo do produto não volta."""
    itens = list(compra.itens.select_related('produto'))
    produtos = _travar_produtos(compra.loja, {item.produto_id for item in itens})
    retirar = defaultdict(Decimal)
    for item in itens:
        retirar[item.produto_id] += item.quantidade
    for produto_id, quantidade in retirar.items():
        produto = produtos[produto_id]
        if produto.controla_estoque and produto.quantidade_estoque < quantidade:
            raise EstoqueJaUsado(produto)
        _mexer_no_estoque(produto, -quantidade)
    registrar_alteracao(
        loja=compra.loja, usuario=usuario, acao=Acao.COMPRA_EXCLUIDA,
        descricao=f"Compra #{compra.pk}{_de(compra.fornecedor)} · {reais(compra.valor_total)}",
        detalhes={'itens': _descrever_itens(compra), 'data': compra.data.isoformat()},
    )
    compra.delete()


@transaction.atomic
def registrar_despesa(*, loja, data, categoria, valor, descricao='', usuario=None):
    despesa = Despesa.objects.create(
        loja=loja, data=data, categoria=categoria, descricao=descricao, valor=valor, usuario=usuario,
    )
    registrar_alteracao(
        loja=loja, usuario=usuario, acao=Acao.DESPESA_REGISTRADA, descricao=_resumo_da_despesa(despesa),
    )
    return despesa


@transaction.atomic
def excluir_despesa(despesa, *, usuario=None):
    registrar_alteracao(
        loja=despesa.loja, usuario=usuario, acao=Acao.DESPESA_EXCLUIDA, descricao=_resumo_da_despesa(despesa),
        detalhes={'data': despesa.data.isoformat(), 'descricao': despesa.descricao},
    )
    despesa.delete()


@transaction.atomic
def registrar_perda(*, loja, produto_id, quantidade, data, motivo, usuario=None):
    """Baixa do estoque o que se perdeu. Vale pelo custo do produto hoje."""
    produto = _travar_produtos(loja, {produto_id})[produto_id]
    _conferir_quantidade(produto, quantidade)
    if produto.controla_estoque and produto.quantidade_estoque < quantidade:
        raise EstoqueNaoCobreAPerda(produto, formatar_quantidade(produto.quantidade_estoque, produto.unidade))
    perda = Perda.objects.create(
        loja=loja, produto=produto, quantidade=quantidade, custo_unitario=produto.preco_custo, data=data,
        motivo=motivo, usuario=usuario,
    )
    _mexer_no_estoque(produto, -quantidade)
    registrar_alteracao(loja=loja, usuario=usuario, acao=Acao.PERDA_REGISTRADA, descricao=_resumo_da_perda(perda))
    return perda


@transaction.atomic
def excluir_perda(perda, *, usuario=None):
    """Devolve ao estoque o que tinha sido dado como perdido (registrado por engano)."""
    _mexer_no_estoque(perda.produto, perda.quantidade)
    registrar_alteracao(
        loja=perda.loja, usuario=usuario, acao=Acao.PERDA_EXCLUIDA, descricao=_resumo_da_perda(perda),
        detalhes={'data': perda.data.isoformat()},
    )
    perda.delete()


def _travar_produtos(loja, ids):
    produtos = {p.pk: p for p in Produto.objects.select_for_update().filter(loja=loja, pk__in=ids).order_by('pk')}
    if len(produtos) != len(ids):
        raise ProdutoDeOutraLoja()
    return produtos


def _conferir_quantidade(produto, quantidade):
    if not quantidade_aceita(quantidade, produto.unidade):
        raise QuantidadeInvalidaParaUnidade(produto)


def _mexer_no_estoque(produto, quantidade):
    """Soma (ou tira, se negativa) do estoque do produto que tem controle de estoque."""
    if produto.controla_estoque:
        Produto.objects.filter(pk=produto.pk).update(quantidade_estoque=F('quantidade_estoque') + quantidade)
        produto.refresh_from_db(fields=['quantidade_estoque'])


def _descrever_itens(compra):
    return [
        f"{descrever_item(item.quantidade, item.produto.unidade, item.produto.nome)} a {reais(item.custo_unitario)}"
        for item in compra.itens.select_related('produto')
    ]


def _de(fornecedor):
    return f" · {fornecedor}" if fornecedor else ''


def _resumo_da_despesa(despesa):
    return f"{despesa.categoria}{_de(despesa.descricao)} · {reais(despesa.valor)}"


def _resumo_da_perda(perda):
    item = descrever_item(perda.quantidade, perda.produto.unidade, perda.produto.nome)
    return f"{item} · {perda.motivo} · {reais(perda.valor)}"
