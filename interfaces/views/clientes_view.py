from django.contrib import messages
from django.shortcuts import render, redirect
from application.clientes.selectors import buscar_clientes, clientes_do_usuario
from application.clientes.services import cadastrar_cliente
from infrastructure.models import Cliente
from interfaces.decorators import loja_required
from interfaces.forms import BuscaClientesForm, ClienteForm
from interfaces.views.comum import executar_formulario, primeiro_erro

TEMPLATE_CLIENTES = 'interfaces/clientes.html'


@loja_required
def clientes_view(request):
    if request.method == 'POST':
        form = ClienteForm(request.POST, instance=Cliente(loja=request.user.loja))
        executar_formulario(
            request, form,
            acao=lambda: cadastrar_cliente(form.instance),
            mensagem_sucesso="Cliente cadastrado com sucesso!",
        )
        return redirect('clientes')

    busca = BuscaClientesForm(request.GET)
    if not busca.is_valid():
        messages.error(request, primeiro_erro(busca))
        return redirect('clientes')

    termo = busca.cleaned_data['q']
    context = {
        'clientes': buscar_clientes(clientes_do_usuario(request.user), termo),
        'filtro_busca': termo,
    }
    return render(request, TEMPLATE_CLIENTES, context)
