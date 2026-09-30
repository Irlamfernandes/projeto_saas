"""Vendas com vários itens: registrar, editar e cancelar, sempre com estoque, caderneta e histórico em dia.

Regra da caderneta: venda de balcão (sem cliente) é paga na hora. Venda com cliente vai para a caderneta,
menos o que ele pagou no ato — e esse pagamento fica ligado à venda, acompanhando-a se ela mudar de cliente.
O que ficou na caderneta pode ter data para pagar (vencimentos); sem data, fica "sem prazo".
"""
from collections import Counter
from decimal import Decimal
from typing import NamedTuple
from django.db import transaction
from django.db.models import F
from application.auditoria.services import registrar_alteracao
from application.vendas.exceptions import (
    EstoqueInsuficiente, ProdutoNaoEncontrado, QuantidadeFracionada, SenhaIncorreta, VendaSemItens, VendaSemLoja,
)
from application.vendas.opcoes import chave, escolhas_do_item, escolher
from application.vendas.pendencias import a_prazo
from application.vendas.selectors import produtos_da_loja
from infrastructure.models import Acao, ItemVenda, PagamentoCliente, Parcela, Produto, Venda
from infrastructure.models.produto import quantidade_aceita
from infrastructure.models.venda import subtotal
from infrastructure.utils.formatacao import reais


@transaction.atomic
def registrar_venda(*, itens, cliente=None, loja=None, valor_pago=Decimal('0'), forma_pagamento='',
                    observacoes='', vencimentos=(), usuario=None):
    """`itens`: (id do produto, quantidade[, {opção: valor}]). A loja vem do cliente; no balcão, da loja informada."""
    loja = cliente.loja if cliente else loja
    if loja is None:
        raise VendaSemLoja()

    linhas = _reservar_estoque(loja, itens)
    venda = Venda.objects.create(
        loja=loja, cliente=cliente, valor_total=_total(linhas),
        forma_pagamento=forma_pagamento, observacoes=observacoes,
    )
    _criar_itens(venda, linhas)
    if cliente and valor_pago:
        PagamentoCliente.objects.create(
            loja=loja, cliente=cliente, venda=venda, valor=valor_pago, forma_pagamento=forma_pagamento,
            observacao=f"Pagamento no ato da Venda #{venda.pk}",
        )
    _definir_vencimentos(venda, vencimentos)
    registrar_alteracao(
        loja=loja, usuario=usuario, acao=Acao.VENDA_REGISTRADA,
        descricao=f"Venda #{venda.pk} · {_para_quem(venda)} · {reais(venda.valor_total)}",
        detalhes={'venda': fotografar_venda(venda)}, clientes=[venda.cliente],
    )
    return venda


@transaction.atomic
def editar_venda(venda, *, itens, cliente=None, forma_pagamento='', observacoes='', vencimentos=(), usuario=None):
    """Troca itens, cliente e observações. Itens que já estavam na venda (mesmo produto e mesmas opções)
    mantêm o preço e o custo da época."""
    antes = fotografar_venda(venda)
    cliente_antes = venda.cliente
    da_epoca = {(item.produto_id, chave(escolhas_do_item(item.opcoes))): item for item in venda.itens.all()}
    _devolver_estoque(venda)
    venda.itens.all().delete()

    linhas = _reservar_estoque(venda.loja, itens, da_epoca)
    venda.cliente = cliente
    venda.valor_total = _total(linhas)
    venda.forma_pagamento = forma_pagamento
    venda.observacoes = observacoes
    venda.save()
    _criar_itens(venda, linhas)
    _acompanhar_pagamento_no_ato(venda)
    _definir_vencimentos(venda, vencimentos)

    registrar_alteracao(
        loja=venda.loja, usuario=usuario, acao=Acao.VENDA_EDITADA,
        descricao=f"Venda #{venda.pk} · {_para_quem(venda)} · {reais(antes['total'])} → {reais(venda.valor_total)}",
        detalhes={'antes': antes, 'depois': fotografar_venda(venda)}, clientes=[cliente_antes, venda.cliente],
    )
    return venda


@transaction.atomic
def cancelar_venda(venda, *, usuario, senha, motivo):
    """Exige a senha de quem cancela. Devolve o estoque e apaga a venda (com o pagamento feito no ato);
    a cópia completa fica no registro de alterações."""
    if not usuario.check_password(senha):
        raise SenhaIncorreta()

    foto = fotografar_venda(venda)
    _devolver_estoque(venda)
    registrar_alteracao(
        loja=venda.loja, usuario=usuario, acao=Acao.VENDA_CANCELADA,
        descricao=f"Venda #{venda.pk} · {_para_quem(venda)} · {reais(venda.valor_total)} · motivo: {motivo}",
        detalhes={'venda': foto, 'motivo': motivo}, clientes=[venda.cliente],
    )
    venda.delete()


def fotografar_venda(venda):
    """Cópia legível da venda para o histórico (sobrevive ao cancelamento)."""
    return {
        'id': venda.pk,
        'data': venda.data_venda.isoformat(),
        'cliente': venda.cliente.nome if venda.cliente else None,
        'total': str(venda.valor_total),
        'forma_pagamento': venda.get_forma_pagamento_display(),
        'observacoes': venda.observacoes,
        'itens': [
            {
                'produto': item.nome, 'quantidade': str(item.quantidade.normalize()),
                'unidade': item.produto.unidade, 'preco_unitario': str(item.preco_unitario),
            }
            for item in venda.itens.select_related('produto')
        ],
        'pago_no_ato': [str(pagamento.valor) for pagamento in venda.pagamentos_no_ato.all()],
        'vencimentos': [parcela.vencimento.isoformat() for parcela in venda.parcelas.all()],
    }


class Linha(NamedTuple):
    produto: Produto
    quantidade: Decimal
    preco: Decimal
    custo: Decimal
    opcoes: list


def _reservar_estoque(loja, itens, da_epoca=None):
    """Trava os produtos, confere e baixa o estoque. Retorna uma Linha por produto + escolha de opções.

    `itens`: (id do produto, quantidade) ou (id do produto, quantidade, {opção: valor}); iguais são somados.
    `da_epoca`: {(id do produto, chave das escolhas): item} dos itens que já estavam na venda em edição —
    mantêm o preço, o custo e as opções da época, mesmo que o produto tenha mudado.

    Produto sem controle de estoque é vendido sem conferir nem baixar a quantidade.
    """
    pedidos = _juntar_iguais(itens)
    if not pedidos:
        raise VendaSemItens()

    ids = {produto_id for produto_id, _ in pedidos}
    # Ordem fixa ao travar: duas vendas simultâneas não se bloqueiam mutuamente.
    travados = produtos_da_loja(loja).select_for_update().filter(pk__in=ids).order_by('pk')
    produtos = {produto.pk: produto for produto in travados}
    if len(produtos) != len(ids):
        raise ProdutoNaoEncontrado()

    da_epoca = da_epoca or {}
    linhas = [
        _linha(produtos[produto_id], quantidade, escolhas, da_epoca.get((produto_id, escolhas)))
        for (produto_id, escolhas), quantidade in pedidos.items()
    ]
    quantidades = Counter()
    for linha in linhas:
        quantidades[linha.produto.pk] += linha.quantidade
    for produto in produtos.values():
        if produto.controla_estoque:
            _baixar_estoque(produto, quantidades[produto.pk])
    return linhas


def _juntar_iguais(itens):
    """{(id do produto, chave das escolhas): quantidade somada}."""
    pedidos = Counter()
    for produto_id, quantidade, *escolhas in itens:
        pedidos[(produto_id, chave(escolhas[0] if escolhas else {}))] += quantidade
    return pedidos


def _linha(produto, quantidade, escolhas, anterior):
    if not quantidade_aceita(quantidade, produto.unidade):
        raise QuantidadeFracionada(produto)
    if anterior:
        return Linha(produto, quantidade, anterior.preco_unitario, anterior.custo_unitario, anterior.opcoes)
    opcoes, acrescimo = escolher(produto, dict(escolhas))
    return Linha(produto, quantidade, produto.preco_venda + acrescimo, produto.preco_custo, opcoes)


def _baixar_estoque(produto, quantidade):
    if produto.quantidade_estoque < quantidade:
        raise EstoqueInsuficiente(produto)
    produto.quantidade_estoque -= quantidade
    produto.save(update_fields=['quantidade_estoque'])


def _devolver_estoque(venda):
    for item in venda.itens.all():
        Produto.objects.filter(pk=item.produto_id, controla_estoque=True).update(
            quantidade_estoque=F('quantidade_estoque') + item.quantidade,
        )


def _criar_itens(venda, linhas):
    for linha in linhas:
        ItemVenda.objects.create(
            venda=venda, produto=linha.produto, quantidade=linha.quantidade, preco_unitario=linha.preco,
            custo_unitario=linha.custo, opcoes=linha.opcoes,
        )


def _acompanhar_pagamento_no_ato(venda):
    """O que foi pago no ato segue a venda: vai para o novo cliente; no balcão (pago na hora) deixa de existir."""
    pagamentos = venda.pagamentos_no_ato.all()
    if venda.cliente is None:
        pagamentos.delete()
    else:
        pagamentos.update(cliente=venda.cliente, forma_pagamento=venda.forma_pagamento)


def _definir_vencimentos(venda, vencimentos):
    """Só há o que vencer se a venda tem cliente e ficou algo na caderneta; senão as datas são descartadas."""
    venda.parcelas.all().delete()
    if venda.cliente is None or a_prazo(venda) <= 0:
        return
    Parcela.objects.bulk_create(Parcela(venda=venda, vencimento=vencimento) for vencimento in sorted(vencimentos))


def _total(linhas):
    return sum((subtotal(linha.quantidade, linha.preco) for linha in linhas), Decimal('0'))


def _para_quem(venda):
    return venda.cliente.nome if venda.cliente else 'Balcão'
