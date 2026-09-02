from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from infrastructure.models.produto import Produto

@login_required
def produtos_view(request):
    loja_usuario = request.user.loja

    produtos = Produto.objects.filter(loja=loja_usuario)

    # --- CAPTURANDO PARÂMETROS DE FILTRO E ORDENAÇÃO ---
    busca = request.GET.get('q', '').strip()
    categoria_filtro = request.GET.get('categoria', '').strip()
    ordenacao = request.GET.get('ordem', '-data_criacao')
    baixo_estoque = request.GET.get('baixo_estoque')

    # Aplicando filtro de busca por nome
    if busca:
        produtos = produtos.filter(nome__icontains=busca)

    # Aplicando filtro por categoria
    if categoria_filtro:
        produtos = produtos.filter(categoria=categoria_filtro)

    # Aplicando filtro de estoque baixo (<= 5 unidades)
    if baixo_estoque:
        produtos = produtos.filter(quantidade_estoque__lte=5)

    # Aplicando ordenação
    if ordenacao in ['nome', '-nome', 'preco_venda', '-preco_venda', 'quantidade_estoque', '-quantidade_estoque', '-data_criacao']:
        produtos = produtos.order_by(ordenacao)
    else:
        produtos = produtos.order_by('-data_criacao')

    if request.method == 'POST':
        nome = request.POST.get('nome')
        categoria = request.POST.get('categoria')
        descricao = request.POST.get('descricao')
        preco_custo = request.POST.get('preco_custo') or 0
        preco_venda = request.POST.get('preco_venda')
        quantidade_estoque = request.POST.get('quantidade_estoque') or 0

        Produto.objects.create(
            loja=loja_usuario,
            nome=nome,
            categoria=categoria,
            descricao=descricao,
            preco_custo=preco_custo,
            preco_venda=preco_venda,
            quantidade_estoque=quantidade_estoque
        )
        return redirect('produtos')

    categorias_qs = Produto.objects.filter(loja=loja_usuario).exclude(categoria__isnull=True).exclude(categoria__exact='').values_list('categoria', flat=True).distinct()
    categorias_existentes = list(categorias_qs)

    context = {
        'produtos': produtos,
        'categorias_existentes': categorias_existentes,
        'filtro_busca': busca,
        'filtro_categoria': categoria_filtro,
        'filtro_ordem': ordenacao,
        'filtro_baixo_estoque': baixo_estoque,
    }
    return render(request, 'interfaces/produtos.html', context)
