from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
import requests
import os
from infrastructure.models.produto import Produto, ProdutoImagem
from infrastructure.utils.supabase_storage import upload_imagem_supabase

TEMPLATE_EDITAR_PRODUTO = 'interfaces/produto_editar.html'


def _obter_produto_autorizado(user, pk):
    """Busca o produto aplicando restrições de permissão por loja ou superuser."""
    if not user.is_superuser and not user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if user.is_superuser:
        return get_object_or_404(Produto, pk=pk)
    return get_object_or_404(Produto, pk=pk, loja=user.loja)


def _parse_valores_produto(request):
    """Extrai e converte os valores monetários e numéricos do POST."""
    preco_custo_raw = request.POST.get('preco_custo', '0').strip().replace(',', '.')
    preco_custo = Decimal(preco_custo_raw) if preco_custo_raw else Decimal('0.00')

    preco_venda_raw = request.POST.get('preco_venda', '0').strip().replace(',', '.')
    preco_venda = Decimal(preco_venda_raw) if preco_venda_raw else Decimal('0.00')

    margem_lucro_raw = request.POST.get('margem_lucro', '0').strip().replace(',', '.')
    margem_lucro = Decimal(margem_lucro_raw) if margem_lucro_raw else Decimal('0.00')

    qtd_estoque_raw = request.POST.get('quantidade_estoque', '0').strip()
    quantidade_estoque = int(qtd_estoque_raw) if qtd_estoque_raw else 0

    return preco_custo, preco_venda, margem_lucro, quantidade_estoque


def _remover_imagem_supabase(img_url):
    """Remove uma imagem individual diretamente do Storage do Supabase."""
    if not img_url:
        return
    try:
        parsed_path = img_url.split('/storage/v1/object/public/imagens/')
        if len(parsed_path) > 1:
            file_path = parsed_path[1]
            base_url = os.getenv("SUPABASE_URL", "").strip().rstrip('/')
            if base_url.endswith('/rest/v1'):
                base_url = base_url[:-8]
            delete_url = f"{base_url}/storage/v1/object/imagens/{file_path}"
            headers = {
                "apikey": os.getenv("SUPABASE_KEY"),
                "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}"
            }
            requests.delete(delete_url, headers=headers)
    except Exception:
        pass


def _processar_remocao_imagens(request, produto):
    """Processa a exclusão de imagens solicitadas pelo usuário."""
    remover_imagens_raw = request.POST.get('remover_imagens', '').strip()
    imagens_para_remover = [i.strip() for i in remover_imagens_raw.split(',') if i.strip()]
    
    if not imagens_para_remover:
        return

    imagens_objs = ProdutoImagem.objects.filter(id__in=imagens_para_remover, produto=produto)
    for img_obj in imagens_objs:
        _remover_imagem_supabase(img_obj.imagem_url)
        img_obj.delete()


def _processar_novas_imagens(request, produto):
    """Realiza o upload e o registro de novas imagens enviadas."""
    imagens_enviadas = request.FILES.getlist('imagens')
    if not imagens_enviadas:
        return

    for img in imagens_enviadas:
        public_url = upload_imagem_supabase(img, produto.id)
        ProdutoImagem.objects.create(
            produto=produto,
            imagem_url=public_url
        )


@login_required
def produto_editar_view(request, pk):
    produto = _obter_produto_autorizado(request.user, pk)

    if request.method != 'POST':
        return render(request, TEMPLATE_EDITAR_PRODUTO, {'produto': produto})

    codigo_interno = request.POST.get('codigo_interno', '').strip()
    nome = request.POST.get('nome', '').strip()
    categoria = request.POST.get('categoria', '').strip()
    descricao = request.POST.get('descricao', '').strip()
    
    if not nome:
        messages.error(request, "O nome do produto é obrigatório.")
        return redirect('editar_produto', pk=produto.pk)

    if len(codigo_interno) > 50 or len(nome) > 150 or len(categoria) > 100:
        messages.error(request, "Algum dos campos excede o limite máximo de caracteres permitido.")
        return redirect('editar_produto', pk=produto.pk)

    try:
        preco_custo, preco_venda, margem_lucro, quantidade_estoque = _parse_valores_produto(request)
    except (ValueError, InvalidOperation):
        messages.error(request, "Os valores numéricos informados (preços ou estoque) são inválidos.")
        return redirect('editar_produto', pk=produto.pk)

    produto.codigo_interno = codigo_interno or None
    produto.nome = nome
    produto.categoria = categoria or None
    produto.descricao = descricao or None
    produto.preco_custo = preco_custo
    produto.preco_venda = preco_venda
    produto.margem_lucro = margem_lucro
    produto.quantidade_estoque = quantidade_estoque
    
    try:
        produto.full_clean()
        produto.save()

        _processar_remocao_imagens(request, produto)
        _processar_novas_imagens(request, produto)

        messages.success(request, "Produto atualizado com sucesso!")
        return redirect('produtos')
    except ValidationError:
        messages.error(request, "Erro ao validar dados: certifique-se de que preços e estoques não são negativos.")
    except Exception as e:
        messages.error(request, str(e))
    
    return redirect('editar_produto', pk=produto.pk)