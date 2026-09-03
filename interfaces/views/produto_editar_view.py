from decimal import Decimal, InvalidOperation
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
import requests
import os
from infrastructure.models.produto import Produto, ProdutoImagem
from infrastructure.utils.supabase_storage import upload_imagem_supabase

@login_required
def produto_editar_view(request, pk):
    if not request.user.is_superuser and not request.user.loja:
        raise PermissionDenied("Acesso negado: Usuário não está vinculado a nenhuma loja.")

    if request.user.is_superuser:
        produto = get_object_or_404(Produto, pk=pk)
    else:
        produto = get_object_or_404(Produto, pk=pk, loja=request.user.loja)

    if request.method == 'POST':
        codigo_interno = request.POST.get('codigo_interno', '').strip()
        nome = request.POST.get('nome', '').strip()
        categoria = request.POST.get('categoria', '').strip()
        descricao = request.POST.get('descricao', '').strip()
        
        imagens_enviadas = request.FILES.getlist('imagens')
        
        remover_imagens_raw = request.POST.get('remover_imagens', '').strip()
        imagens_para_remover = [i.strip() for i in remover_imagens_raw.split(',') if i.strip()]
        
        if not nome:
            messages.error(request, "O nome do produto é obrigatório.")
            return redirect('editar_produto', pk=produto.pk)

        if len(codigo_interno) > 50 or len(nome) > 150 or len(categoria) > 100:
            messages.error(request, "Algum dos campos excede o limite máximo de caracteres permitido.")
            return redirect('editar_produto', pk=produto.pk)

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
            messages.error(request, "Os valores numéricos informados (preços ou estoque) são inválidos.")
            return redirect('editar_produto', pk=produto.pk)

        produto.codigo_interno = codigo_interno if codigo_interno else None
        produto.nome = nome
        produto.categoria = categoria if categoria else None
        produto.descricao = descricao if descricao else None
        produto.preco_custo = preco_custo
        produto.preco_venda = preco_venda
        produto.margem_lucro = margem_lucro
        produto.quantidade_estoque = quantidade_estoque
        
        try:
            produto.full_clean()
            produto.save()

            if imagens_para_remover:
                imagens_objs = ProdutoImagem.objects.filter(id__in=imagens_para_remover, produto=produto)
                for img_obj in imagens_objs:
                    try:
                        if img_obj.imagem_url:
                            parsed_path = img_obj.imagem_url.split('/storage/v1/object/public/produtos/')
                            if len(parsed_path) > 1:
                                file_path = parsed_path[1]
                                base_url = os.getenv("SUPABASE_URL", "").strip().rstrip('/')
                                if base_url.endswith('/rest/v1'):
                                    base_url = base_url[:-8]
                                delete_url = f"{base_url}/storage/v1/object/produtos/{file_path}"
                                headers = {
                                    "apikey": os.getenv("SUPABASE_KEY"),
                                    "Authorization": f"Bearer {os.getenv('SUPABASE_KEY')}"
                                }
                                requests.delete(delete_url, headers=headers)
                    except Exception:
                        pass
                    
                    img_obj.delete()

            if imagens_enviadas:
                for img in imagens_enviadas:
                    public_url = upload_imagem_supabase(img, produto.id)
                    ProdutoImagem.objects.create(
                        produto=produto,
                        imagem_url=public_url
                    )

            messages.success(request, "Produto atualizado com sucesso!")
            return redirect('produtos')
        except ValidationError as e:
            messages.error(request, "Erro ao validar dados: certifique-se de que preços e estoques não são negativos.")
        except Exception as e:
            messages.error(request, str(e))
        
        return redirect('editar_produto', pk=produto.pk)

    context = {
        'produto': produto
    }
    return render(request, 'interfaces/produto_editar.html', context)