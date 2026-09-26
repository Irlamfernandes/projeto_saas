from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from django.db.models import Q
from application.tenancy import filtrar_por_loja
from infrastructure.models import Cliente


@dataclass(frozen=True)
class Movimento:
    """Linha do extrato da caderneta: uma compra (débito) ou um pagamento (crédito)."""
    tipo: str
    data: datetime
    descricao: str
    valor: Decimal
    itens: tuple = ()
    observacao: str = ''


def clientes_do_usuario(user):
    return filtrar_por_loja(Cliente.objects.all(), user).order_by('nome')


def clientes_da_loja(loja):
    return Cliente.objects.filter(loja=loja).order_by('nome')


def buscar_clientes(clientes, termo=''):
    if termo:
        clientes = clientes.filter(Q(nome__icontains=termo) | Q(telefone__icontains=termo))
    return clientes.order_by('-data_criacao')


def linha_do_tempo(cliente):
    """Compras e pagamentos do cliente, do mais recente para o mais antigo."""
    compras = [
        Movimento(
            tipo='compra',
            data=venda.data_venda,
            descricao=f"Compra de Produtos (Venda #{venda.pk})",
            valor=venda.valor_total,
            itens=tuple(venda.itens.all()),
            observacao=venda.observacoes,
        )
        for venda in cliente.vendas.prefetch_related('itens__produto')
    ]
    pagamentos = [
        Movimento(
            tipo='pagamento',
            data=pagamento.data_pagamento,
            descricao=f"Pagamento Recebido ({pagamento.observacao or 'Caderneta'})",
            valor=pagamento.valor,
        )
        for pagamento in cliente.pagamentos.all()
    ]
    return sorted(compras + pagamentos, key=lambda movimento: movimento.data, reverse=True)
