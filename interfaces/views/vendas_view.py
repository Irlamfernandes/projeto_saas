from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect, get_object_or_404
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from infrastructure.models.venda import Venda, ItemVenda, PagamentoCliente
from infrastructure.models.produto import Produto
from infrastructure.models.cliente import Cliente

@login_required
def vendas_view(request):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_usuario = request.user.loja

    if request.user.is_superuser:
        vendas = Venda.objects.all().order_by('-data_venda')
        produtos = Produto.objects.filter(quantidade_estoque__gt=0)
        clientes = Cliente.objects.all()
    else:
        vendas = Venda.objects.filter(loja=loja_usuario).order_by('-data_venda')
        produtos = Produto.objects.filter(loja=loja_usuario, quantidade_estoque__gt=0)
        clientes = Cliente.objects.filter(loja=loja_usuario)

    if request.method == 'POST':
        cliente_id = request.POST.get('cliente')
        produto_input = request.POST.get('produto', '').strip()
        observacoes = request.POST.get('observacoes', '').strip()

        try:
            quantidade = int(request.POST.get('quantidade', 1))
            if quantidade <= 0:
                raise ValueError("A quantidade deve ser maior que zero.")
        except (TypeError, ValueError):
            messages.error(request, "Quantidade inválida informada.")
            return redirect('vendas')

        try:
            valor_pago_inicial = Decimal(request.POST.get('valor_pago') or '0')
            if valor_pago_inicial < 0:
                raise ValueError("O valor pago não pode ser negativo.")
        except (InvalidOperation, ValueError):
            messages.error(request, "Valor pago inicial inválido.")
            return redirect('vendas')

        try:
            if request.user.is_superuser:
                cliente = get_object_or_404(Cliente, pk=cliente_id)
            else:
                cliente = get_object_or_404(Cliente, pk=cliente_id, loja=loja_usuario)
        except Http404:
            messages.error(request, "Cliente selecionado não foi encontrado.")
            return redirect('vendas')

        base_produtos_query = Produto.objects.all() if request.user.is_superuser else Produto.objects.filter(loja=loja_usuario)
        
        produto_temp = base_produtos_query.filter(
            Q(pk=produto_input) | Q(codigo_interno__iexact=produto_input) | Q(nome__icontains=produto_input)
        ).first()

        if not produto_temp:
            messages.error(request, f"Produto '{produto_input}' não foi encontrado pelo Código Interno ou Nome.")
            return redirect('vendas')

        with transaction.atomic():
            if request.user.is_superuser:
                produto = Produto.objects.select_for_update().get(pk=produto_temp.pk)
            else:
                produto = Produto.objects.select_for_update().get(pk=produto_temp.pk, loja=loja_usuario)

            if produto.quantidade_estoque >= quantidade:
                total_produto = produto.preco_venda * quantidade

                loja_venda = loja_usuario if loja_usuario else getattr(cliente, 'loja', None)

                venda = Venda.objects.create(
                    loja=loja_venda,
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

                if valor_pago_inicial > 0:
                    PagamentoCliente.objects.create(
                        loja=loja_venda,
                        cliente=cliente,
                        valor=valor_pago_inicial,
                        observacao=f"Pagamento no ato da Venda #{venda.id}"
                    )

                produto.quantidade_estoque -= quantidade
                produto.save()
                messages.success(request, "Venda realizada com sucesso!")
            else:
                messages.error(request, f"Estoque insuficiente para '{produto.nome}'. Disponível: {produto.quantidade_estoque}.")
                transaction.set_rollback(True)

        return redirect('vendas')

    context = {
        'vendas': vendas,
        'produtos': produtos,
        'clientes': clientes,
    }
    return render(request, 'interfaces/vendas.html', context)