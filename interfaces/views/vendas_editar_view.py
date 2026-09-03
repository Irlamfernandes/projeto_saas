from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from infrastructure.models.venda import Venda, ItemVenda
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente

@login_required
def venda_editar_view(request, venda_id):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_usuario = request.user.loja

    if request.user.is_superuser:
        venda = get_object_or_404(Venda, pk=venda_id)
        produtos = Produto.objects.all()
        clientes = Cliente.objects.all()
    else:
        venda = get_object_or_404(Venda, pk=venda_id, loja=loja_usuario)
        produtos = Produto.objects.filter(loja=loja_usuario)
        clientes = Cliente.objects.filter(loja=loja_usuario)

    item_atual = venda.itens.first()

    if request.method == 'POST':
        novo_cliente_id = request.POST.get('cliente')
        novo_produto_input = request.POST.get('produto', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()

        try:
            nova_quantidade = int(request.POST.get('quantidade', 1))
            if nova_quantidade <= 0:
                raise ValueError("A quantidade deve ser maior que zero.")
        except (TypeError, ValueError):
            messages.error(request, "Quantidade inválida informada.")
            return redirect('venda_editar', venda_id=venda.id)

        try:
            if novo_cliente_id:
                if request.user.is_superuser:
                    novo_cliente = get_object_or_404(Cliente, pk=novo_cliente_id)
                else:
                    novo_cliente = get_object_or_404(Cliente, pk=novo_cliente_id, loja=loja_usuario)
            else:
                novo_cliente = None
        except Http404:
            messages.error(request, "Cliente selecionado não foi encontrado.")
            return redirect('venda_editar', venda_id=venda.id)

        base_produtos_query = Produto.objects.all() if request.user.is_superuser else Produto.objects.filter(loja=loja_usuario)
        
        novo_produto = base_produtos_query.filter(
            Q(pk=novo_produto_input) | Q(codigo_interno__iexact=novo_produto_input) | Q(nome__icontains=novo_produto_input)
        ).first()

        if not novo_produto:
            messages.error(request, f"Produto '{novo_produto_input}' não foi encontrado pelo Código Interno ou Nome.")
            return redirect('venda_editar', venda_id=venda.id)

        with transaction.atomic():
            if item_atual:
                produto_antigo_bloqueado = Produto.objects.select_for_update().get(pk=item_atual.produto.pk)
                produto_antigo_bloqueado.quantidade_estoque += item_atual.quantidade
                produto_antigo_bloqueado.save()

            novo_produto_bloqueado = Produto.objects.select_for_update().get(pk=novo_produto.pk)

            if novo_produto_bloqueado.quantidade_estoque >= nova_quantidade:
                novo_produto_bloqueado.quantidade_estoque -= nova_quantidade
                novo_produto_bloqueado.save()

                novo_total = novo_produto_bloqueado.preco_venda * nova_quantidade

                venda.cliente = novo_cliente
                venda.valor_total = novo_total
                venda.observacoes = observacoes
                if not request.user.is_superuser:
                    venda.loja = loja_usuario
                venda.save()

                if item_atual:
                    item_atual.produto = novo_produto_bloqueado
                    item_atual.quantidade = nova_quantidade
                    item_atual.preco_unitario = novo_produto_bloqueado.preco_venda
                    item_atual.save()
                else:
                    ItemVenda.objects.create(
                        venda=venda,
                        produto=novo_produto_bloqueado,
                        quantidade=nova_quantidade,
                        preco_unitario=novo_produto_bloqueado.preco_venda
                    )
                
                messages.success(request, "Venda atualizada com sucesso!")
            else:
                messages.error(request, f"Estoque insuficiente para o produto '{novo_produto_bloqueado.nome}'. Disponível: {novo_produto_bloqueado.quantidade_estoque}.")
                transaction.set_rollback(True)
                return redirect('venda_editar', venda_id=venda.id)

        return redirect('vendas')

    context = {
        'venda': venda,
        'produtos': produtos,
        'clientes': clientes,
        'item_atual': item_atual,
    }
    return render(request, 'interfaces/venda_editar.html', context)