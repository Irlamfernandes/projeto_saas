from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import PagamentoCliente

@login_required
def extrato_cliente_view(request, cliente_id):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        cliente = get_object_or_404(Cliente, pk=cliente_id)
        loja_contexto = cliente.loja
    else:
        cliente = get_object_or_404(Cliente, pk=cliente_id, loja=request.user.loja)
        loja_contexto = request.user.loja

    if request.method == 'POST':
        try:
            valor_raw = request.POST.get('valor', '0').strip().replace(',', '.')
            valor = Decimal(valor_raw)
        except (ValueError, InvalidOperation):
            messages.error(request, "O valor informado para o pagamento é inválido.")
            return redirect('extrato_cliente', cliente_id=cliente.id)

        observacao = request.POST.get('observacao', 'Pagamento na caderneta').strip()

        if len(observacao) > 255:
            messages.error(request, "A observação excede o limite máximo de 255 caracteres.")
            return redirect('extrato_cliente', cliente_id=cliente.id)

        pagamento = PagamentoCliente(
            loja=loja_contexto,
            cliente=cliente,
            valor=valor,
            observacao=observacao if observacao else 'Pagamento na caderneta'
        )

        try:
            pagamento.full_clean()
            pagamento.save()
            messages.success(request, "Pagamento registrado com sucesso!")
        except ValidationError:
            messages.error(request, "Erro ao validar os dados do pagamento. Verifique se o valor é positivo.")

        return redirect('extrato_cliente', cliente_id=cliente.id)

    compras = list(cliente.vendas.prefetch_related('itens__produto').all())
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