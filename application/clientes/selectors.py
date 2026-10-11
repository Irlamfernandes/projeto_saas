from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from django.db.models import Q
from application.tenancy import filtrar_por_loja
from application.vendas.pendencias import pendencias_do_cliente
from infrastructure.models import Cliente
from infrastructure.utils.cpf import so_digitos


@dataclass(frozen=True)
class Movimento:
    """Linha do extrato da caderneta: uma compra (débito) ou um pagamento (crédito)."""
    tipo: str
    data: datetime
    descricao: str
    valor: Decimal
    itens: tuple = ()
    observacao: str = ''
    pendencias: tuple = ()  # compra: o que falta de cada parcela (vazio = paga no ato)


def clientes_do_usuario(user):
    return filtrar_por_loja(Cliente.objects.all(), user).order_by('nome')


def clientes_da_loja(loja):
    return Cliente.objects.filter(loja=loja).order_by('nome')


def buscar_clientes(clientes, termo=''):
    if termo:
        filtro = Q(nome__icontains=termo) | Q(telefone__icontains=termo)
        digitos = so_digitos(termo)
        if digitos:  # CPF digitado com ou sem pontos e traço
            filtro |= Q(cpf__contains=digitos)
        clientes = clientes.filter(filtro)
    return clientes.order_by('-data_criacao')


def linha_do_tempo(cliente):
    """Compras e pagamentos do cliente, do mais recente para o mais antigo."""
    por_venda = {}
    for pendencia in pendencias_do_cliente(cliente):
        por_venda.setdefault(pendencia.venda.pk, []).append(pendencia)
    compras = [
        Movimento(
            tipo='compra',
            data=venda.data_venda,
            descricao=f"Compra de Produtos (Venda #{venda.pk})",
            valor=venda.valor_total,
            itens=tuple(venda.itens.all()),
            observacao=venda.observacoes,
            pendencias=tuple(por_venda.get(venda.pk, ())),
        )
        for venda in cliente.vendas.prefetch_related('itens__produto')
    ]
    pagamentos = [
        Movimento(
            tipo='pagamento',
            data=pagamento.data_pagamento,
            descricao=f"Pagamento Recebido ({pagamento.observacao or 'Caderneta'})",
            valor=pagamento.valor,
            observacao=pagamento.get_forma_pagamento_display(),
        )
        for pagamento in cliente.pagamentos.all()
    ]
    return sorted(compras + pagamentos, key=lambda movimento: movimento.data, reverse=True)
