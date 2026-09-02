from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from infrastructure.models.venda import Venda, ItemVenda
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import PagamentoCliente

@login_required
def vendas_view(request):
    loja_usuario = request.user.loja

    vendas = Venda.objects.filter(loja=loja_usuario).order_by('-data_venda')
    produtos = Produto.objects.filter(loja=loja_usuario, quantidade_estoque__gt=0)
    clientes = Cliente.objects.filter(loja=loja_usuario)

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_id = request.POST.get('produto')
        quantidade = int(request.POST.get('quantidade', 1))
        valor_pago_inicial = Decimal(request.POST.get('valor_pago') or '0')
        observacoes = request.POST.get('observacoes', '')

        cliente = get_object_or_404(Cliente, pk=cliente_id, loja=loja_usuario)
        produto = get_object_or_404(Produto, pk=produto_id, loja=loja_usuario)

        if produto.quantidade_estoque >= quantidade:
            with transaction.atomic():
                total_produto = produto.preco_venda * quantidade

                venda = Venda.objects.create(
                    loja=loja_usuario,
                    cliente=cliente,
                    valor_total=total_produto,
                    observacoes=observacoes
                )

                ItemVenda.objects.create(
                    venda=venda,
                    produto=produto,
                    quantidade=quantidade,
                    preco_unitario=produto.preco_venda
                )

                if cliente and valor_pago_inicial > 0:
                    PagamentoCliente.objects.create(
                        loja=loja_usuario,
                        cliente=cliente,
                        valor=valor_pago_inicial,
                        observacao=f"Pagamento no ato da Venda #{venda.id}"
                    )

                produto.quantidade_estoque -= quantidade
                produto.save()

        return redirect('vendas')

    context = {
        'vendas': vendas,
        'produtos': produtos,
        'clientes': clientes,
    }
    return render(request, 'interfaces/vendas.html', context)