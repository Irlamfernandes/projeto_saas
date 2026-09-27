from datetime import timedelta
from django.shortcuts import render
from application.a_receber.selectors import clientes_a_cobrar
from application.gastos.selectors import Mes, resultado_do_mes
from application.relatorios.indicadores import indicadores_do_painel
from application.relatorios.periodos import hoje_local
from application.relatorios.produtos import previsao_de_reposicao
from application.relatorios.selectors import montar_painel
from application.relatorios.vendas import faturamento_por_dia, mais_vendidos, mapa_de_horarios, vendido_x_recebido
from interfaces import graficos
from interfaces.cobrancas import cobrancas_na_tela
from interfaces.decorators import loja_required
from interfaces.forms import LimiteEstoqueForm
from interfaces.views.planos_view import conferir_pix_abertos

DIAS_DO_GRAFICO = 30
ITENS_NO_RANKING = 5
DIAS_PARA_REPOR = 7
OPCOES_DE_LIMITE = (1, 2, 3, 5, 10, 20)


@loja_required
def dashboard_view(request):
    conferir_pix_abertos(request)  # quem pagou o plano e fechou a tela já entra com ele renovado
    user = request.user
    limite = LimiteEstoqueForm(request.GET).limite()
    top = mais_vendidos(user, inicio=hoje_local() - timedelta(days=DIAS_DO_GRAFICO - 1), limite=ITENS_NO_RANKING)
    context = {
        **montar_painel(user, limite).como_contexto(),
        'limite_estoque': limite,
        'opcoes_de_limite': OPCOES_DE_LIMITE,
        'hoje_por_extenso': graficos.data_por_extenso(hoje_local()),
        'indicadores': indicadores_do_painel(user),
        'grafico_faturamento': graficos.diario(faturamento_por_dia(user, DIAS_DO_GRAFICO)),
        'mais_vendidos': top,
        'grafico_mais_vendidos': graficos.ranking([p.nome for p in top], [float(p.quantidade) for p in top], 'Quantidade'),
        'grafico_fluxo': graficos.vendido_x_recebido(vendido_x_recebido(user, meses=6)),
        'mapa': mapa_de_horarios(user),
        'reposicao': previsao_de_reposicao(user, horizonte=DIAS_PARA_REPOR)[:ITENS_NO_RANKING],
        'cobrancas': cobrancas_na_tela(clientes_a_cobrar(user, hoje_local())),
        'mes_atual': Mes.de(hoje_local()),
        'resultado_do_mes': resultado_do_mes(user, Mes.de(hoje_local())),
    }
    return render(request, 'interfaces/dashboard.html', context)
