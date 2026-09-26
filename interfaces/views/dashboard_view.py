from django.shortcuts import render
from application.relatorios.selectors import montar_painel
from interfaces.decorators import loja_required
from interfaces.forms import LimiteEstoqueForm


@loja_required
def dashboard_view(request):
    limite = LimiteEstoqueForm(request.GET).limite()
    painel = montar_painel(request.user, limite)
    context = {**painel.como_contexto(), 'limite_estoque': limite}
    return render(request, 'interfaces/dashboard.html', context)
