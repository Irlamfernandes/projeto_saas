from django.contrib import messages
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from application.contas.services import definir_senha_definitiva
from interfaces.forms import NovaSenhaForm
from interfaces.views.comum import redirecionar_apos_login

TEMPLATE_ALTERAR_SENHA = 'interfaces/alterar_senha.html'


@login_required
def alterar_senha_view(request):
    """Troca obrigatória da senha temporária (primeiro acesso/reset) ou troca voluntária."""
    contexto = {'troca_obrigatoria': request.user.deve_trocar_senha}

    if request.method != 'POST':
        return render(request, TEMPLATE_ALTERAR_SENHA, contexto)

    form = NovaSenhaForm(request.user, request.POST)
    if not form.is_valid():
        return render(request, TEMPLATE_ALTERAR_SENHA, {**contexto, 'erros': form.lista_de_erros()})

    definir_senha_definitiva(request.user, form.cleaned_data['nova_senha'])
    update_session_auth_hash(request, request.user)
    messages.success(request, "Senha alterada com sucesso!")
    return redirecionar_apos_login(request, request.user)
