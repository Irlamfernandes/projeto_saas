from django.shortcuts import get_object_or_404, redirect, render
from application.produtos.selectors import MAXIMO_DE_FOTOS, fotos_disponiveis, produtos_do_usuario
from application.produtos.services import atualizar_produto
from interfaces.decorators import loja_required
from interfaces.forms import EditarProdutoForm
from interfaces.views.comum import executar_formulario

TEMPLATE_EDITAR_PRODUTO = 'interfaces/produto_editar.html'


@loja_required
def produto_editar_view(request, pk):
    produto = get_object_or_404(produtos_do_usuario(request.user), pk=pk)

    if request.method != 'POST':
        return render(request, TEMPLATE_EDITAR_PRODUTO, {
            'produto': produto,
            'maximo_de_fotos': MAXIMO_DE_FOTOS,
            'fotos_disponiveis': fotos_disponiveis(produto),
        })

    form = EditarProdutoForm(request.POST, request.FILES, instance=produto)
    salvou = executar_formulario(
        request, form,
        acao=lambda: atualizar_produto(**form.parametros(), usuario=request.user),
        mensagem_sucesso="Produto atualizado com sucesso!",
    )
    if salvou:
        return redirect('produtos')
    return redirect('editar_produto', pk=produto.pk)
