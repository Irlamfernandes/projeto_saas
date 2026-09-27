from django.shortcuts import render, redirect
from application.clientes.selectors import clientes_do_usuario
from application.vendas.selectors import produtos_em_estoque_do_usuario, vendas_do_usuario
from application.vendas.services import registrar_venda
from infrastructure.models import FormaDePagamento
from interfaces.catalogo import catalogo_para_venda
from interfaces.decorators import loja_required
from interfaces.forms import NovaVendaForm
from interfaces.views.comum import executar_formulario, paginar


@loja_required
def vendas_view(request):
    clientes = clientes_do_usuario(request.user)

    if request.method == 'POST':
        form = NovaVendaForm(request.POST, clientes=clientes)
        executar_formulario(
            request, form,
            acao=lambda: registrar_venda(**form.parametros(), loja=request.user.loja, usuario=request.user),
            mensagem_sucesso="Venda realizada com sucesso!",
        )
        return redirect('vendas')

    vendas = paginar(request, vendas_do_usuario(request.user))
    context = {
        'vendas': vendas,
        'page_obj': vendas,
        'catalogo': catalogo_para_venda(produtos_em_estoque_do_usuario(request.user).order_by('nome')),
        'clientes': clientes.com_saldo(),
        'formas_de_pagamento': FormaDePagamento.choices,
    }
    return render(request, 'interfaces/vendas.html', context)
