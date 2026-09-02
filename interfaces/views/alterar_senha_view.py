from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required
def alterar_senha_view(request):
    # Se por acaso o usuário não precisar trocar e tentar acessar via URL, manda pro dashboard
    if not request.user.deve_trocar_senha:
        return redirect('dashboard')

    if request.method == 'POST':
        nova_senha = request.POST.get('nova_senha')
        confirmacao_senha = request.POST.get('confirmacao_senha')
        
        if nova_senha and nova_senha == confirmacao_senha:
            # Salva a nova senha escolhida
            request.user.set_password(nova_senha)
            # Desativa a flag de troca obrigatória
            request.user.deve_trocar_senha = False
            request.user.save()
            
            # Atualiza a sessão para o usuário não deslogar ao mudar a senha
            from django.contrib.auth import update_session_auth_hash
            update_session_auth_hash(request, request.user)
            
            return redirect('dashboard')
        else:
            error = "As senhas não coincidem ou estão vazias."
            return render(request, 'interfaces/alterar_senha.html', {'error': error})

    return render(request, 'interfaces/alterar_senha.html')