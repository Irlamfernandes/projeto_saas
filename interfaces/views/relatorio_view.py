from django.shortcuts import render
from application.relatorios.selectors import montar_relatorio
from interfaces.decorators import loja_required
from interfaces.forms import PeriodoForm

TEMPLATE_RELATORIO = 'interfaces/relatorio.html'


@loja_required
def relatorio_view(request):
    inicio, fim = PeriodoForm(request.GET).intervalo()
    relatorio = montar_relatorio(request.user, inicio, fim)
    context = {**relatorio.como_contexto(), 'data_inicio': inicio, 'data_fim': fim}
    return render(request, TEMPLATE_RELATORIO, context)
