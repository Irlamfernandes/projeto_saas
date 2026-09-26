from application.clientes.exceptions import ClienteSemLoja
from infrastructure.models import PagamentoCliente

OBSERVACAO_PADRAO_PAGAMENTO = 'Pagamento na caderneta'


def cadastrar_cliente(cliente):
    if cliente.loja_id is None:
        raise ClienteSemLoja()
    cliente.save()
    return cliente


def registrar_pagamento(cliente, *, valor, observacao=''):
    """Abate `valor` do saldo do cliente na caderneta da loja dele."""
    return PagamentoCliente.objects.create(
        loja=cliente.loja,
        cliente=cliente,
        valor=valor,
        observacao=observacao or OBSERVACAO_PADRAO_PAGAMENTO,
    )
