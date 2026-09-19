from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

TEMPLATE_CONTA = 'interfaces/conta.html'

@login_required
def conta_view(request):
    """Exibe o painel de gerenciamento da conta do usuário logado."""
    loja = getattr(request.user, 'loja', None)
    
    return render(request, TEMPLATE_CONTA, {
        'loja': loja
    })