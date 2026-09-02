from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from infrastructure.models.produto import Produto

@login_required
def produto_editar_view(request, pk):
    loja_usuario = request.user.loja
    
    # Garante que o produto pertence estritamente à loja do usuário logado
    produto = get_object_or_404(Produto, pk=pk, loja=loja_usuario)

    if request.method == 'POST':
        produto.nome = request.POST.get('nome')
        produto.categoria = request.POST.get('categoria')
        produto.descricao = request.POST.get('descricao')
        produto.preco_custo = request.POST.get('preco_custo') or 0
        produto.preco_venda = request.POST.get('preco_venda')
        produto.quantidade_estoque = request.POST.get('quantidade_estoque') or 0
        
        produto.save()
        
    return redirect('produtos')