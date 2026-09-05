from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import update_session_auth_hash
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password

TEMPLATE_ALTERAR_SENHA = 'interfaces/alterar_senha.html'

@login_required
def alterar_senha_view(request):
    if not request.user.deve_trocar_senha:
        return redirect('dashboard')

    if request.method == 'POST':
        nova_senha = request.POST.get('nova_senha', '')
        confirmacao_senha = request.POST.get('confirmacao_senha', '')
        
        if len(nova_senha) > 128 or len(confirmacao_senha) > 128:
            messages.error(request, "A senha excede o limite máximo de caracteres permitido.")
            return render(request, TEMPLATE_ALTERAR_SENHA)

        if not nova_senha or not confirmacao_senha:
            messages.error(request, "Os campos de senha não podem estar vazios.")
            return render(request, TEMPLATE_ALTERAR_SENHA)

        if nova_senha != confirmacao_senha:
            messages.error(request, "As senhas não coincidem.")
            return render(request, TEMPLATE_ALTERAR_SENHA)

        try:
            validate_password(nova_senha, user=request.user)
        except ValidationError as e:
            for error in e.messages:
                messages.error(request, error)
            return render(request, TEMPLATE_ALTERAR_SENHA)

        request.user.set_password(nova_senha)
        request.user.deve_trocar_senha = False
        request.user.save()
        
        update_session_auth_hash(request, request.user)
        
        messages.success(request, "Senha alterada com sucesso!")
        return redirect('dashboard')

    return render(request, TEMPLATE_ALTERAR_SENHA)