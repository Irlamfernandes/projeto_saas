from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.produto import Produto

@login_required
def produtos_view(request):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        produtos = Produto.objects.all()
        loja_contexto = None
    else:
        produtos = Produto.objects.filter(loja=request.user.loja)
        loja_contexto = request.user.loja

    busca = request.GET.get('q', '').strip()
    categoria_filtro = request.GET.get('categoria', '').strip()
    ordenacao = request.GET.get('ordem', '-data_criacao').strip()
    baixo_estoque = request.GET.get('baixo_estoque')

    if busca:
        if len(busca) > 100:
            messages.error(request, "O termo de busca é muito longo.")
            return redirect('produtos')
        produtos = produtos.filter(nome__icontains=busca)

    if categoria_filtro:
        if len(categoria_filtro) > 100:
            messages.error(request, "O filtro de categoria é inválido.")
            return redirect('produtos')
        produtos = produtos.filter(categoria=categoria_filtro)

    if baixo_estoque:
        produtos = produtos.filter(quantidade_estoque__lte=5)

    campos_permitidos = {
        'nome', '-nome', 
        'preco_venda', '-preco_venda', 
        'quantidade_estoque', '-quantidade_estoque', 
        '-data_criacao', 'data_criacao'
    }
    if ordenacao in campos_permitidos:
        produtos = produtos.order_by(ordenacao)
    else:
        produtos = produtos.order_by('-data_criacao')

    if request.method == 'POST':
        nome = request.POST.get('nome', '').strip()
        categoria = request.POST.get('categoria', '').strip()
        descricao = request.POST.get('descricao', '').strip()

        if not nome:
            messages.error(request, "O nome do produto é obrigatório.")
            return redirect('produtos')

        if len(nome) > 150 or len(categoria) > 100:
            messages.error(request, "O nome ou a categoria excedem o limite máximo permitido.")
            return redirect('produtos')

        try:
            preco_custo_raw = request.POST.get('preco_custo', '0').strip().replace(',', '.')
            preco_custo = Decimal(preco_custo_raw) if preco_custo_raw else Decimal('0.00')

            preco_venda_raw = request.POST.get('preco_venda', '0').strip().replace(',', '.')
            preco_venda = Decimal(preco_venda_raw) if preco_venda_raw else Decimal('0.00')

            margem_lucro_raw = request.POST.get('margem_lucro', '0').strip().replace(',', '.')
            margem_lucro = Decimal(margem_lucro_raw) if margem_lucro_raw else Decimal('0.00')

            qtd_estoque_raw = request.POST.get('quantidade_estoque', '0').strip()
            quantidade_estoque = int(qtd_estoque_raw) if qtd_estoque_raw else 0
        except (ValueError, InvalidOperation):
            messages.error(request, "Os valores numéricos informados são inválidos.")
            return redirect('produtos')

        if request.user.is_superuser and not loja_contexto:
            messages.error(request, "Superusuários devem associar o produto a uma loja específica.")
            return redirect('produtos')

        novo_produto = Produto(
            loja=loja_contexto,
            nome=nome,
            categoria=categoria if categoria else None,
            descricao=descricao if descricao else None,
            preco_custo=preco_custo,
            preco_venda=preco_venda,
            margem_lucro=margem_lucro,
            quantidade_estoque=quantidade_estoque
        )

        try:
            novo_produto.full_clean()
            novo_produto.save()
            messages.success(request, "Produto cadastrado com sucesso!")
        except ValidationError:
            messages.error(request, "Erro ao validar os dados do produto. Verifique preços e estoque.")

        return redirect('produtos')

    if request.user.is_superuser:
        categorias_qs = Produto.objects.all()
    else:
        categorias_qs = Produto.objects.filter(loja=request.user.loja)

    categorias_existentes = list(
        categorias_qs.exclude(categoria__isnull=True)
                     .exclude(categoria__exact='')
                     .values_list('categoria', flat=True)
                     .distinct()
    )

    context = {
        'produtos': produtos,
        'categorias_existentes': categorias_existentes,
        'filtro_busca': busca,
        'filtro_categoria': categoria_filtro,
        'filtro_ordem': ordenacao,
        'filtro_baixo_estoque': baixo_estoque,
    }
    return render(request, 'interfaces/produtos.html', context)