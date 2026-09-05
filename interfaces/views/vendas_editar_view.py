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

TEMPLATE_VENDA_EDITAR = 'interfaces/venda_editar.html'


def _verificar_permissao_e_obter_contexto(user, venda_id):
    """Valida permissões e retorna a venda, produtos e clientes permitidos."""
    if not user.is_superuser and not user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    loja_usuario = user.loja
    if user.is_superuser:
        venda = get_object_or_404(Venda, pk=venda_id)
        produtos = Produto.objects.all()
        clientes = Cliente.objects.all()
    else:
        venda = get_object_or_404(Venda, pk=venda_id, loja=loja_usuario)
        produtos = Produto.objects.filter(loja=loja_usuario)
        clientes = Cliente.objects.filter(loja=loja_usuario)

    return venda, produtos, clientes, loja_usuario


def _parse_quantidade(request):
    """Extrai e valida a quantidade informada no POST."""
    try:
        quantidade = int(request.POST.get('quantidade', 1))
        if quantidade <= 0:
            raise ValueError()
        return quantidade, None
    except (TypeError, ValueError):
        return None, "Quantidade inválida informada."


def _obter_cliente_por_request(request, loja_usuario):
    """Busca o cliente com base nas permissões do usuário."""
    cliente_id = request.POST.get('cliente')
    if not cliente_id:
        return None, None

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

    produto = base_query.filter(
        Q(pk=produto_input) | Q(codigo_interno__iexact=produto_input) | Q(nome__icontains=produto_input)
    ).first()

    if not produto:
        return None, f"Produto '{produto_input}' não foi encontrado pelo Código Interno ou Nome."
    return produto, None


def _atualizar_transacao_venda(venda, item_atual, novo_produto, nova_quantidade, novo_cliente, observacoes, loja_usuario, is_superuser):
    """Executa a transação atômica de devolução de estoque antigo, baixa do novo e atualização da venda."""
    with transaction.atomic():
        if item_atual:
            produto_antigo = Produto.objects.select_for_update().get(pk=item_atual.produto.pk)
            produto_antigo.quantidade_estoque += item_atual.quantidade
            produto_antigo.save()

        produto_novo = Produto.objects.select_for_update().get(pk=novo_produto.pk)

        if produto_novo.quantidade_estoque < nova_quantidade:
            transaction.set_rollback(True)
            return False, f"Estoque insuficiente para o produto '{produto_novo.nome}'. Disponível: {produto_novo.quantidade_estoque}."

        produto_novo.quantidade_estoque -= nova_quantidade
        produto_novo.save()

        venda.cliente = novo_cliente
        venda.valor_total = produto_novo.preco_venda * nova_quantidade
        venda.observacoes = observacoes
        if not is_superuser:
            venda.loja = loja_usuario
        venda.save()

        if item_atual:
            item_atual.produto = produto_novo
            item_atual.quantidade = nova_quantidade
            item_atual.preco_unitario = produto_novo.preco_venda
            item_atual.save()
        else:
            ItemVenda.objects.create(
                venda=venda,
                produto=produto_novo,
                quantidade=nova_quantidade,
                preco_unitario=produto_novo.preco_venda
            )

    return True, None


@login_required
def venda_editar_view(request, venda_id):
    venda, produtos, clientes, loja_usuario = _verificar_permissao_e_obter_contexto(request.user, venda_id)
    item_atual = venda.itens.first()

    if request.method == 'POST':
        nova_quantidade, erro_qtd = _parse_quantidade(request)
        if erro_qtd:
            messages.error(request, erro_qtd)
            return redirect('venda_editar', venda_id=venda.id)

        novo_cliente, erro_cliente = _obter_cliente_por_request(request, loja_usuario)
        if erro_cliente:
            messages.error(request, erro_cliente)
            return redirect('venda_editar', venda_id=venda.id)

        novo_produto, erro_produto = _obter_produto_por_request(request, loja_usuario)
        if erro_produto:
            messages.error(request, erro_produto)
            return redirect('venda_editar', venda_id=venda.id)

        observacoes = request.POST.get('observacoes', '').strip()
        sucesso, erro_transacao = _atualizar_transacao_venda(
            venda, item_atual, novo_produto, nova_quantidade, 
            novo_cliente, observacoes, loja_usuario, request.user.is_superuser
        )

        if not sucesso:
            messages.error(request, erro_transacao)
            return redirect('venda_editar', venda_id=venda.id)

        messages.success(request, "Venda atualizada com sucesso!")
        return redirect('vendas')

    context = {
        'venda': venda,
        'produtos': produtos,
        'clientes': clientes,
        'item_atual': item_atual,
    }
    return render(request, TEMPLATE_VENDA_EDITAR, context)