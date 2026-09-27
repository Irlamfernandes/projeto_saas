from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from application.clientes.selectors import clientes_da_loja
from application.vendas.selectors import produtos_da_loja, vendas_do_usuario
from application.vendas.services import cancelar_venda, editar_venda
from infrastructure.models import FormaDePagamento
from interfaces.catalogo import catalogo_para_venda, itens_da_venda
from interfaces.decorators import loja_required
from interfaces.forms import CancelarVendaForm, EditarVendaForm
from interfaces.views.comum import executar_formulario

TEMPLATE_VENDA_EDITAR = 'interfaces/venda_editar.html'


@loja_required
def venda_editar_view(request, venda_id):
    venda = get_object_or_404(vendas_do_usuario(request.user), pk=venda_id)
    clientes = clientes_da_loja(venda.loja)

    if request.method != 'POST':
        reservados = {item.produto_id: item.quantidade for item in venda.itens.all()}
        pago_no_ato = sum(p.valor for p in venda.pagamentos_no_ato.all())
        context = {
            'venda': venda,
            'catalogo': catalogo_para_venda(produtos_da_loja(venda.loja).order_by('nome'), reservados),
            'itens_iniciais': itens_da_venda(venda),
            'clientes': clientes,
            'formas_de_pagamento': FormaDePagamento.choices,
            'pago_no_ato': pago_no_ato,
            'forma_obrigatoria': venda.cliente_id is None or pago_no_ato > 0,
            'vencimentos': [parcela.vencimento for parcela in venda.parcelas.all()],
        }
        return render(request, TEMPLATE_VENDA_EDITAR, context)

    form = EditarVendaForm(request.POST, clientes=clientes, venda=venda)
    salvou = executar_formulario(
        request, form,
        acao=lambda: editar_venda(venda, **form.parametros(), usuario=request.user),
        mensagem_sucesso="Venda atualizada com sucesso!",
    )
    if salvou:
        return redirect('vendas')
    return redirect('venda_editar', venda_id=venda.pk)


@loja_required
@require_POST
def venda_cancelar_view(request, venda_id):
    venda = get_object_or_404(vendas_do_usuario(request.user), pk=venda_id)
    numero = venda.pk
    form = CancelarVendaForm(request.POST)
    cancelou = executar_formulario(
        request, form,
        acao=lambda: cancelar_venda(venda, usuario=request.user, **form.parametros()),
        mensagem_sucesso=f"Venda #{numero} cancelada. O estoque foi devolvido.",
    )
    if cancelou:
        return redirect('vendas')
    return redirect('venda_editar', venda_id=numero)
