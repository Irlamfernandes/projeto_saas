"""Vendas com vários itens: registrar, editar e cancelar, sempre com estoque, caderneta e histórico em dia.

Regra da caderneta: venda de balcão (sem cliente) é paga na hora. Venda com cliente vai para a caderneta,
menos o que ele pagou no ato — e esse pagamento fica ligado à venda, acompanhando-a se ela mudar de cliente.
O que ficou na caderneta pode ter data para pagar (vencimentos); sem data, fica "sem prazo".
"""
from collections import Counter
from decimal import Decimal
from django.db import transaction
from django.db.models import F
from application.auditoria.services import registrar_alteracao
from application.vendas.exceptions import (
    EstoqueInsuficiente, ProdutoNaoEncontrado, QuantidadeFracionada, SenhaIncorreta, VendaSemItens, VendaSemLoja,
)
from application.vendas.pendencias import a_prazo
from application.vendas.selectors import produtos_da_loja
from infrastructure.models import Acao, ItemVenda, PagamentoCliente, Parcela, Produto, Venda
from infrastructure.models.produto import quantidade_aceita
from infrastructure.models.venda import subtotal
from infrastructure.utils.formatacao import reais


@transaction.atomic
def registrar_venda(*, itens, cliente=None, loja=None, valor_pago=Decimal('0'), forma_pagamento='',
                    observacoes='', vencimentos=(), usuario=None):
    """`itens`: pares (id do produto, quantidade). A loja vem do cliente; no balcão, da loja informada."""
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
        detalhes={'venda': fotografar_venda(venda)},
    )
    return venda


@transaction.atomic
def editar_venda(venda, *, itens, cliente=None, forma_pagamento='', observacoes='', vencimentos=(), usuario=None):
    """Troca itens, cliente e observações. Produtos que já estavam na venda mantêm o preço da época."""
    antes = fotografar_venda(venda)
    precos_da_epoca = {item.produto_id: item.preco_unitario for item in venda.itens.all()}
    _devolver_estoque(venda)
    venda.itens.all().delete()

    linhas = _reservar_estoque(venda.loja, itens, precos_da_epoca)
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
        detalhes={'antes': antes, 'depois': fotografar_venda(venda)},
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
        detalhes={'venda': foto, 'motivo': motivo},
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
                'produto': item.produto.nome, 'quantidade': str(item.quantidade.normalize()),
                'unidade': item.produto.unidade, 'preco_unitario': str(item.preco_unitario),
            }
            for item in venda.itens.select_related('produto')
        ],
        'pago_no_ato': [str(pagamento.valor) for pagamento in venda.pagamentos_no_ato.all()],
        'vencimentos': [parcela.vencimento.isoformat() for parcela in venda.parcelas.all()],
    }


def _reservar_estoque(loja, itens, precos=None):
    """Trava os produtos, confere e baixa o estoque. Retorna [(produto, quantidade, preço unitário)].

    Produto sem controle de estoque é vendido sem conferir nem baixar a quantidade.
    """
    quantidades = Counter()
    for produto_id, quantidade in itens:
        quantidades[produto_id] += quantidade
    if not quantidades:
        raise VendaSemItens()

    # Ordem fixa ao travar: duas vendas simultâneas não se bloqueiam mutuamente.
    produtos = list(produtos_da_loja(loja).select_for_update().filter(pk__in=quantidades).order_by('pk'))
    if len(produtos) != len(quantidades):
        raise ProdutoNaoEncontrado()

    precos = precos or {}
    linhas = []
    for produto in produtos:
        quantidade = quantidades[produto.pk]
        if not quantidade_aceita(quantidade, produto.unidade):
            raise QuantidadeFracionada(produto)
        if produto.controla_estoque:
            _baixar_estoque(produto, quantidade)
        linhas.append((produto, quantidade, precos.get(produto.pk, produto.preco_venda)))
    return linhas


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
    for produto, quantidade, preco in linhas:
        ItemVenda.objects.create(venda=venda, produto=produto, quantidade=quantidade, preco_unitario=preco)


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
    return sum((subtotal(quantidade, preco) for _, quantidade, preco in linhas), Decimal('0'))


def _para_quem(venda):
    return venda.cliente.nome if venda.cliente else 'Balcão'
