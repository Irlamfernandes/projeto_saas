from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db import transaction
from infrastructure.models.venda import Venda, ItemVenda
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente

@login_required
def venda_editar_view(request, venda_id):
    loja_usuario = request.user.loja
    venda = get_object_or_404(Venda, pk=venda_id, loja=loja_usuario)
    
    produtos = Produto.objects.filter(loja=loja_usuario)
    clientes = Cliente.objects.filter(loja=loja_usuario)
    item_atual = venda.itens.first()

    if request.method == 'POST':
        novo_cliente_id = request.POST.get('cliente')
        novo_produto_id = request.POST.get('produto')
        nova_quantidade = int(request.POST.get('quantidade', 1))
        observacoes = request.POST.get('observacoes', '')

        novo_cliente = get_object_or_404(Cliente, pk=novo_cliente_id, loja=loja_usuario) if novo_cliente_id else None
        novo_produto = get_object_or_404(Produto, pk=novo_produto_id, loja=loja_usuario)

        with transaction.atomic():
            if item_atual:
                item_atual.produto.quantidade_estoque += item_atual.quantidade
                item_atual.produto.save()

            if novo_produto.quantidade_estoque >= nova_quantidade:
                novo_produto.quantidade_estoque -= nova_quantidade
                novo_produto.save()

                novo_total = novo_produto.preco_venda * nova_quantidade

                venda.cliente = novo_cliente
                venda.valor_total = novo_total
                venda.observacoes = observacoes
                venda.save()

                if item_atual:
                    item_atual.produto = novo_produto
                    item_atual.quantidade = nova_quantidade
                    item_atual.preco_unitario = novo_produto.preco_venda
                    item_atual.save()
                else:
                    ItemVenda.objects.create(
                        venda=venda,
                        produto=novo_produto,
                        quantidade=nova_quantidade,
                        preco_unitario=novo_produto.preco_venda
                    )
            else:
                return redirect('venda_editar', venda_id=venda.id)

        return redirect('vendas')

    context = {
        'venda': venda,
        'produtos': produtos,
        'clientes': clientes,
        'item_atual': item_atual,
    }
    return render(request, 'interfaces/venda_editar.html', context)