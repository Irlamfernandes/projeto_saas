from django.shortcuts import get_object_or_404, redirect
from application.clientes.selectors import clientes_do_usuario
from interfaces.decorators import loja_required
from interfaces.forms import ClienteForm
from interfaces.views.comum import executar_formulario


@loja_required
def cliente_editar_view(request, pk):
    """A edição acontece num modal da listagem; aqui só se processa o POST."""
    cliente = get_object_or_404(clientes_do_usuario(request.user), pk=pk)

    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=cliente)
        executar_formulario(request, form, acao=form.save, mensagem_sucesso="Cliente atualizado com sucesso!")

    return redirect('clientes')
