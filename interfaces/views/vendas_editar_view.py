from django.shortcuts import render, redirect, get_object_or_404
from application.vendas.selectors import clientes_da_loja, produtos_da_loja, vendas_do_usuario
from application.vendas.services import editar_venda
from interfaces.decorators import loja_required
from interfaces.forms import EditarVendaForm
from interfaces.views.comum import executar_formulario

TEMPLATE_VENDA_EDITAR = 'interfaces/venda_editar.html'


@loja_required
def venda_editar_view(request, venda_id):
    venda = get_object_or_404(vendas_do_usuario(request.user), pk=venda_id)
    clientes = clientes_da_loja(venda.loja)

    if request.method != 'POST':
        context = {
            'venda': venda,
            'produtos': produtos_da_loja(venda.loja),
            'clientes': clientes,
            'item_atual': venda.itens.first(),
        }
        return render(request, TEMPLATE_VENDA_EDITAR, context)

    form = EditarVendaForm(request.POST, clientes=clientes)
    salvou = executar_formulario(
        request, form,
        acao=lambda: editar_venda(venda, **form.parametros()),
        mensagem_sucesso="Venda atualizada com sucesso!",
    )
    if salvou:
        return redirect('vendas')
    return redirect('venda_editar', venda_id=venda.pk)
