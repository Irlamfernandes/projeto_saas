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


def _verificar_permissao_e_obter_contexto(user):
    """Valida permissões e retorna os querysets contextuais de vendas, produtos e clientes."""
    if not user.is_superuser and not user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_usuario = user.loja
    if user.is_superuser:
        vendas = Venda.objects.all().order_by('-data_venda')
        produtos = Produto.objects.filter(quantidade_estoque__gt=0)
        clientes = Cliente.objects.all()
    else:
        vendas = Venda.objects.filter(loja=loja_usuario).order_by('-data_venda')
        produtos = Produto.objects.filter(loja=loja_usuario, quantidade_estoque__gt=0)
        clientes = Cliente.objects.filter(loja=loja_usuario)

    return vendas, produtos, clientes, loja_usuario


def _parse_quantidade(request):
    """Extrai e valida a quantidade informada no POST."""
    try:
        quantidade = int(request.POST.get('quantidade', 1))
        if quantidade <= 0:
            return None, "A quantidade deve ser maior que zero."
        return quantidade, None
    except (TypeError, ValueError):
        return None, "Quantidade inválida informada."


def _parse_valor_pago(request):
    """Extrai e valida o valor pago inicial informando no POST."""
    try:
        valor = Decimal(request.POST.get('valor_pago') or '0')
        if valor < 0:
            return None, "O valor pago não pode ser negativo."
        return valor, None
    except (InvalidOperation, ValueError):
        return None, "Valor pago inicial inválido."


def _obter_cliente_por_request(request, loja_usuario):
    """Busca o cliente com base nas permissões do usuário."""
    cliente_id = request.POST.get('cliente')
    try:
        if request.user.is_superuser:
            return get_object_or_404(Cliente, pk=cliente_id), None
        return get_object_or_404(Cliente, pk=cliente_id, loja=loja_usuario), None
    except Http404:
        return None, "Cliente selecionado não foi encontrado."


def _obter_produto_por_request(request, loja_usuario):
    """Busca o produto por ID, código interno ou nome."""
    produto_input = request.POST.get('produto', '').strip()
    base_query = Produto.objects.all() if request.user.is_superuser else Produto.objects.filter(loja=loja_usuario)

    produto_temp = base_query.filter(
        Q(pk=produto_input) | Q(codigo_interno__iexact=produto_input) | Q(nome__icontains=produto_input)
    ).first()

    if not produto_temp:
        return None, f"Produto '{produto_input}' não foi encontrado pelo Código Interno ou Nome."
    return produto_temp, None


def _processar_criacao_venda(user, loja_usuario, cliente, produto_temp, quantidade, valor_pago_inicial, observacoes):
    """Executa a transação atômica para registrar a venda, atualizar estoque e pagamentos."""
    with transaction.atomic():
        if user.is_superuser:
            produto = Produto.objects.select_for_update().get(pk=produto_temp.pk)
        else:
            produto = Produto.objects.select_for_update().get(pk=produto_temp.pk, loja=loja_usuario)

        if produto.quantidade_estoque < quantidade:
            transaction.set_rollback(True)
            return False, f"Estoque insuficiente para '{produto.nome}'. Disponível: {produto.quantidade_estoque}."

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

    return True, "Venda realizada com sucesso!"


@login_required
def vendas_view(request):
    vendas, produtos, clientes, loja_usuario = _verificar_permissao_e_obter_contexto(request.user)

    if request.method == 'POST':
        quantidade, erro_qtd = _parse_quantidade(request)
        if erro_qtd:
            messages.error(request, erro_qtd)
            return redirect('vendas')

        valor_pago_inicial, erro_valor = _parse_valor_pago(request)
        if erro_valor:
            messages.error(request, erro_valor)
            return redirect('vendas')

        cliente, erro_cliente = _obter_cliente_por_request(request, loja_usuario)
        if erro_cliente:
            messages.error(request, erro_cliente)
            return redirect('vendas')

        produto_temp, erro_produto = _obter_produto_por_request(request, loja_usuario)
        if erro_produto:
            messages.error(request, erro_produto)
            return redirect('vendas')

        observacoes = request.POST.get('observacoes', '').strip()
        sucesso, mensagem = _processar_criacao_venda(
            request.user, loja_usuario, cliente, produto_temp, 
            quantidade, valor_pago_inicial, observacoes
        )

        if sucesso:
            messages.success(request, mensagem)
        else:
            messages.error(request, mensagem)

        return redirect('vendas')

    context = {
        'vendas': vendas,
        'produtos': produtos,
        'clientes': clientes,
    }
    return render(request, 'interfaces/vendas.html', context)