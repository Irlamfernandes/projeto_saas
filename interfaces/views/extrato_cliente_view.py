from django.shortcuts import render, redirect, get_object_or_404
from application.clientes.selectors import clientes_do_usuario, linha_do_tempo
from application.clientes.services import registrar_pagamento
from interfaces.decorators import loja_required
from interfaces.forms import PagamentoForm
from interfaces.views.comum import executar_formulario

TEMPLATE_EXTRATO_CLIENTE = 'interfaces/extrato_cliente.html'


@loja_required
def extrato_cliente_view(request, cliente_id):
    clientes = clientes_do_usuario(request.user).com_saldo().select_related('loja')
    cliente = get_object_or_404(clientes, pk=cliente_id)

    if request.method == 'POST':
        form = PagamentoForm(request.POST)
        executar_formulario(
            request, form,
            acao=lambda: registrar_pagamento(cliente, **form.parametros()),
            mensagem_sucesso="Pagamento registrado com sucesso!",
        )
        return redirect('extrato_cliente', cliente_id=cliente.pk)

    context = {
        'cliente': cliente,
        'timeline': linha_do_tempo(cliente),
    }
    return render(request, TEMPLATE_EXTRATO_CLIENTE, context)
