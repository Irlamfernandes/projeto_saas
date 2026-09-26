from django.shortcuts import render, redirect
from application.vendas.selectors import (
    clientes_do_usuario, produtos_em_estoque_do_usuario, vendas_do_usuario,
)
from application.vendas.services import registrar_venda
from interfaces.decorators import loja_required
from interfaces.forms import NovaVendaForm
from interfaces.views.comum import executar_formulario


@loja_required
def vendas_view(request):
    clientes = clientes_do_usuario(request.user)

    if request.method == 'POST':
        form = NovaVendaForm(request.POST, clientes=clientes)
        executar_formulario(
            request, form,
            acao=lambda: registrar_venda(**form.parametros()),
            mensagem_sucesso="Venda realizada com sucesso!",
        )
        return redirect('vendas')

    context = {
        'vendas': vendas_do_usuario(request.user),
        'produtos': produtos_em_estoque_do_usuario(request.user),
        'clientes': clientes,
    }
    return render(request, 'interfaces/vendas.html', context)
