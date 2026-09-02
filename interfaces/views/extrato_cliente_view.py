from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import PagamentoCliente


@login_required
def extrato_cliente_view(request, cliente_id):
    loja_usuario = request.user.loja
    cliente = get_object_or_404(Cliente, pk=cliente_id, loja=loja_usuario)

    if request.method == 'POST':
        valor = Decimal(request.POST.get('valor') or '0')
        observacao = request.POST.get('observacao', 'Pagamento na caderneta')
        if valor > 0:
            PagamentoCliente.objects.create(
                loja=loja_usuario,
                cliente=cliente,
                valor=valor,
                observacao=observacao
            )
        return redirect('extrato_cliente', cliente_id=cliente.id)

    compras = list(cliente.vendas.all())
    pagamentos = list(cliente.pagamentos.all())

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

    context = {
        'cliente': cliente,
        'timeline': timeline,
    }
    return render(request, 'interfaces/extrato_cliente.html', context)