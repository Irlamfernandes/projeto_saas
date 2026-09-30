from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from application.clientes.selectors import clientes_do_usuario, linha_do_tempo
from application.clientes.services import apagar_dados_pessoais, registrar_pagamento
from infrastructure.models import FormaDePagamento
from interfaces.decorators import loja_required
from interfaces.forms import ApagarDadosDoClienteForm, PagamentoForm
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
            acao=lambda: registrar_pagamento(cliente, **form.parametros(), usuario=request.user),
            mensagem_sucesso="Pagamento registrado com sucesso!",
        )
        return redirect('extrato_cliente', cliente_id=cliente.pk)

    context = {
        'cliente': cliente,
        'timeline': linha_do_tempo(cliente),
        'formas_de_pagamento': FormaDePagamento.choices,
    }
    return render(request, TEMPLATE_EXTRATO_CLIENTE, context)


@loja_required(trava_plano_vencido=False)  # direito do titular (LGPD): vale mesmo com o plano vencido
@require_POST
def cliente_apagar_dados_view(request, cliente_id):
    cliente = get_object_or_404(clientes_do_usuario(request.user), pk=cliente_id)
    form = ApagarDadosDoClienteForm(request.POST)
    executar_formulario(
        request, form,
        acao=lambda: apagar_dados_pessoais(cliente, usuario=request.user, **form.parametros()),
        mensagem_sucesso="Dados pessoais apagados. As compras e os pagamentos continuam nos relatórios, sem o nome.",
    )
    return redirect('extrato_cliente', cliente_id=cliente.pk)
