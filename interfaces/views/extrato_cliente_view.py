from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from interfaces.decorators import loja_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import PagamentoCliente

TEMPLATE_EXTRATO_CLIENTE = 'interfaces/extrato_cliente.html'


def _obter_cliente_e_loja(user, cliente_id):
    """Retorna o cliente verificado e o contexto da loja de acordo com as permissões."""
    if user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        return cliente, cliente.loja
    
    cliente = get_object_or_404(Cliente, pk=cliente_id, loja=user.loja)
    return cliente, user.loja


def _processar_pagamento(request, cliente, loja_contexto):
    """Processa a requisição POST para registrar um novo pagamento."""
    try:
        valor_raw = request.POST.get('valor', '0').strip().replace(',', '.')
        valor = Decimal(valor_raw)
    except (ValueError, InvalidOperation):
        messages.error(request, "O valor informado para o pagamento é inválido.")
        return

    observacao = request.POST.get('observacao', 'Pagamento na caderneta').strip()
    if len(observacao) > 255:
        messages.error(request, "A observação excede o limite máximo de 255 caracteres.")
        return

    pagamento = PagamentoCliente(
        loja=loja_contexto,
        cliente=cliente,
        valor=valor,
        observacao=observacao or 'Pagamento na caderneta'
    )

    try:
        pagamento.full_clean()
        pagamento.save()
        messages.success(request, "Pagamento registrado com sucesso!")
    except ValidationError:
        messages.error(request, "Erro ao validar os dados do pagamento. Verifique se o valor é positivo.")


def _construir_timeline(cliente):
    """Constrói e ordena a timeline combinando compras e pagamentos."""
    compras = cliente.vendas.prefetch_related('itens__produto').all()
    pagamentos = cliente.pagamentos.all()

    timeline = []
    for c in compras:
        timeline.append({
            'tipo': 'compra',
            'data': c.data_venda,
            'descricao': f"Compra de Produtos (Venda #{c.id})",
            'valor': c.valor_total,
            'detalhes': c.itens.all(),
            'obs': c.observacoes
        })

    for p in pagamentos:
        timeline.append({
            'tipo': 'pagamento',
            'data': p.data_pagamento,
            'descricao': f"Pagamento Recebido ({p.observacao or 'Caderneta'})",
            'valor': p.valor,
            'detalhes': None,
            'obs': None
        })

    timeline.sort(key=lambda x: x['data'], reverse=True)
    return timeline


@loja_required
def extrato_cliente_view(request, cliente_id):
    cliente, loja_contexto = _obter_cliente_e_loja(request.user, cliente_id)

    if request.method == 'POST':
        _processar_pagamento(request, cliente, loja_contexto)
        return redirect('extrato_cliente', cliente_id=cliente.id)

    context = {
        'cliente': cliente,
        'timeline': _construir_timeline(cliente),
    }
    return render(request, TEMPLATE_EXTRATO_CLIENTE, context)