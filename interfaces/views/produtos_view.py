from django.contrib import messages
from django.shortcuts import render, redirect
from application.produtos.selectors import categorias_em_uso, filtrar_produtos, produtos_do_usuario
from application.produtos.services import cadastrar_produto
from infrastructure.models import Produto
from interfaces.decorators import loja_required
from interfaces.forms import FiltroProdutosForm, ProdutoForm
from interfaces.views.comum import executar_formulario, primeiro_erro

TEMPLATE_PRODUTOS = 'interfaces/produtos.html'


@loja_required
def produtos_view(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=Produto(loja=request.user.loja))
        executar_formulario(
            request, form,
            acao=lambda: cadastrar_produto(**form.parametros()),
            mensagem_sucesso="Produto e imagens cadastrados com sucesso!",
        )
        return redirect('produtos')

    filtro = FiltroProdutosForm(request.GET)
    if not filtro.is_valid():
        messages.error(request, primeiro_erro(filtro))
        return redirect('produtos')

    produtos = produtos_do_usuario(request.user)
    criterios = filtro.criterios()
    context = {
        'produtos': filtrar_produtos(produtos, **criterios),
        'categorias_existentes': categorias_em_uso(produtos),
        'filtro_busca': criterios['busca'],
        'filtro_categoria': criterios['categoria'],
        'filtro_ordem': criterios['ordem'],
        'filtro_baixo_estoque': criterios['baixo_estoque'],
    }
    return render(request, TEMPLATE_PRODUTOS, context)
