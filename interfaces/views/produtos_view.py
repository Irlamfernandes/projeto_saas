from decimal import Decimal, InvalidOperation
from django.shortcuts import render, redirect
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from infrastructure.models.produto import Produto, ProdutoImagem
from infrastructure.utils.supabase_storage import upload_imagem_supabase

TEMPLATE_PRODUTOS = 'interfaces/produtos.html'


def _obter_produtos_base(user):
    """Retorna o queryset base e o contexto de loja dependendo das permissões do usuário."""
    if not user.is_superuser and not user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if user.is_superuser:
        return Produto.objects.all(), None
    return Produto.objects.filter(loja=user.loja), user.loja


def _aplicar_filtros_e_ordenacao(produtos, request):
    """Aplica busca por texto, categoria, estoque baixo e ordenação no queryset."""
    busca = request.GET.get('q', '').strip()
    categoria_filtro = request.GET.get('categoria', '').strip()
    ordenacao = request.GET.get('ordem', '-data_criacao').strip()
    baixo_estoque = request.GET.get('baixo_estoque')

    if busca:
        if len(busca) > 100:
            return None, "O termo de busca é muito longo."
        produtos = produtos.filter(Q(nome__icontains=busca) | Q(codigo_interno__icontains=busca))

    if categoria_filtro:
        if len(categoria_filtro) > 100:
            return None, "O filtro de categoria é inválido."
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

    return produtos, None


def _parse_valores_criacao_produto(request):
    """Extrai e converte os valores numéricos enviados via POST."""
    try:
        preco_custo_raw = request.POST.get('preco_custo', '0').strip().replace(',', '.')
        preco_custo = Decimal(preco_custo_raw) if preco_custo_raw else Decimal('0.00')

        preco_venda_raw = request.POST.get('preco_venda', '0').strip().replace(',', '.')
        preco_venda = Decimal(preco_venda_raw) if preco_venda_raw else Decimal('0.00')

        margem_lucro_raw = request.POST.get('margem_lucro', '0').strip().replace(',', '.')
        margem_lucro = Decimal(margem_lucro_raw) if margem_lucro_raw else Decimal('0.00')

        qtd_estoque_raw = request.POST.get('quantidade_estoque', '0').strip()
        quantidade_estoque = int(qtd_estoque_raw) if qtd_estoque_raw else 0

        return preco_custo, preco_venda, margem_lucro, quantidade_estoque, None
    except (ValueError, InvalidOperation):
        return None, None, None, None, "Os valores numéricos informados são inválidos."


def _processar_criacao_produto(request, loja_contexto):
    """Gerencia a criação de um novo produto e o upload de suas imagens."""
    codigo_interno = request.POST.get('codigo_interno', '').strip()
    nome = request.POST.get('nome', '').strip()
    categoria = request.POST.get('categoria', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    imagens_enviadas = request.FILES.getlist('imagens')

    if not nome:
        return "O nome do produto é obrigatório."

    if len(codigo_interno) > 50 or len(nome) > 150 or len(categoria) > 100:
        return "Algum dos campos excede o limite máximo de caracteres permitido."

    if request.user.is_superuser and not loja_contexto:
        return "Superusuários devem associar o produto a uma loja específica."

    preco_custo, preco_venda, margem_lucro, quantidade_estoque, erro_parse = _parse_valores_criacao_produto(request)
    if erro_parse:
        return erro_parse

    novo_produto = Produto(
        loja=loja_contexto,
        codigo_interno=codigo_interno or None,
        nome=nome,
        categoria=categoria or None,
        descricao=descricao or None,
        preco_custo=preco_custo,
        preco_venda=preco_venda,
        margem_lucro=margem_lucro,
        quantidade_estoque=quantidade_estoque
    )

    try:
        novo_produto.full_clean()
        novo_produto.save()

        for img in imagens_enviadas:
            public_url = upload_imagem_supabase(img, novo_produto.id)
            ProdutoImagem.objects.create(produto=novo_produto, imagem_url=public_url)

        return None
    except ValidationError:
        return "Erro ao validar os dados do produto. Verifique preços e estoque."
    except Exception as e:
        return str(e)


@login_required
def produtos_view(request):
    produtos_qs, loja_contexto = _obter_produtos_base(request.user)

    if request.method == 'POST':
        erro = _processar_criacao_produto(request, loja_contexto)
        if erro:
            messages.error(request, erro)
        else:
            messages.success(request, "Produto e imagens cadastrados com sucesso!")
        return redirect('produtos')

    produtos_filtrados, erro_filtro = _aplicar_filtros_e_ordenacao(produtos_qs, request)
    if erro_filtro:
        messages.error(request, erro_filtro)
        return redirect('produtos')

    categorias_existentes = list(
        produtos_qs.exclude(categoria__isnull=True)
                   .exclude(categoria__exact='')
                   .values_list('categoria', flat=True)
                   .distinct()
    )

    context = {
        'produtos': produtos_filtrados,
        'categorias_existentes': categorias_existentes,
        'filtro_busca': request.GET.get('q', '').strip(),
        'filtro_categoria': request.GET.get('categoria', '').strip(),
        'filtro_ordem': request.GET.get('ordem', '-data_criacao').strip(),
        'filtro_baixo_estoque': request.GET.get('baixo_estoque'),
    }
    return render(request, TEMPLATE_PRODUTOS, context)