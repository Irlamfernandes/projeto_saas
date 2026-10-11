from django.contrib import messages
from django.shortcuts import render, redirect
from application.produtos.selectors import MAXIMO_DE_FOTOS, categorias_em_uso, filtrar_produtos, produtos_do_usuario
from application.produtos.services import cadastrar_produto
from infrastructure.models import Produto
from interfaces.decorators import loja_required
from interfaces.forms import FiltroProdutosForm, ProdutoForm
from interfaces.forms.produto_form import TAMANHO_MAXIMO_MB
from interfaces.views.comum import executar_formulario, paginar, primeiro_erro

TEMPLATE_PRODUTOS = 'interfaces/produtos.html'


@loja_required
def produtos_view(request):
    if request.method == 'POST':
        form = ProdutoForm(request.POST, request.FILES, instance=Produto(loja=request.user.loja))
        executar_formulario(
            request, form,
            acao=lambda: cadastrar_produto(**form.parametros(), usuario=request.user),
            mensagem_sucesso="Produto e imagens cadastrados com sucesso!",
        )
        return redirect('produtos')

    filtro = FiltroProdutosForm(request.GET)
    if not filtro.is_valid():
        messages.error(request, primeiro_erro(filtro))
        return redirect('produtos')

    produtos = produtos_do_usuario(request.user)
    criterios = filtro.criterios()
    pagina = paginar(request, filtrar_produtos(produtos, **criterios))
    context = {
        'produtos': pagina,
        'page_obj': pagina,
        'categorias_existentes': categorias_em_uso(produtos),
        'filtro_busca': criterios['busca'],
        'filtro_categoria': criterios['categoria'],
        'filtro_ordem': criterios['ordem'],
        'filtro_baixo_estoque': criterios['baixo_estoque'],
        'maximo_de_fotos': MAXIMO_DE_FOTOS,
        'tamanho_maximo_mb': TAMANHO_MAXIMO_MB,
    }
    return render(request, TEMPLATE_PRODUTOS, context)
