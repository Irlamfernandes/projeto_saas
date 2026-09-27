"""Páginas de relatórios por assunto: vendas, produtos, clientes/caderneta e alterações."""
from django.shortcuts import render
from application.auditoria.selectors import registros_do_usuario
from application.relatorios.pagamentos import recebido_por_forma
from application.relatorios.clientes import clientes_sumidos, idade_das_dividas, melhores_clientes
from application.relatorios.produtos import curva_abc, lucro_estimado, previsao_de_reposicao, produtos_parados
from application.relatorios.vendas import (
    faturamento_por_dia, faturamento_por_mes, mais_vendidos, mapa_de_horarios, vendido_x_recebido,
)
from interfaces import graficos
from interfaces.decorators import loja_required
from interfaces.forms import PeriodoForm, escolher_dias
from interfaces.views.comum import paginar
from infrastructure.models import Acao


def _base(request, aba):
    inicio, fim = PeriodoForm(request.GET).intervalo_ou_ultimos(30)
    return inicio, fim, {'aba': aba, 'data_inicio': inicio, 'data_fim': fim}


@loja_required
def relatorios_vendas_view(request):
    inicio, fim, context = _base(request, 'vendas')
    dias = escolher_dias(request.GET.get('dias'), (30, 90), 30)
    ranking = mais_vendidos(request.user, inicio, fim, limite=10)
    formas, recebido = recebido_por_forma(request.user, inicio, fim)
    context.update({
        'dias': dias,
        'manter': {'dias': dias},
        'grafico_diario': graficos.diario(faturamento_por_dia(request.user, dias)),
        'grafico_mensal': graficos.mensal(faturamento_por_mes(request.user, meses=12)),
        'mais_vendidos': ranking,
        'grafico_mais_vendidos': graficos.ranking([p.nome for p in ranking], [float(p.quantidade) for p in ranking], 'Quantidade'),
        'mapa': mapa_de_horarios(request.user),
        'formas_de_pagamento': formas,
        'total_recebido': recebido,
        'grafico_formas': graficos.ranking([f.forma for f in formas], [f.valor for f in formas], 'Recebido'),
    })
    return render(request, 'interfaces/relatorios_vendas.html', context)


@loja_required
def relatorios_produtos_view(request):
    inicio, fim, context = _base(request, 'produtos')
    dias_parado = escolher_dias(request.GET.get('parado'), (30, 60, 90), 60)
    lucro = lucro_estimado(request.user, inicio, fim)
    linhas_abc, resumo_abc = curva_abc(request.user, inicio, fim)
    context.update({
        'lucro': lucro,
        'grafico_lucro': graficos.ranking([c.nome for c in lucro.categorias], [c.lucro for c in lucro.categorias], 'Lucro'),
        'curva_abc': linhas_abc,
        'resumo_abc': resumo_abc,
        'dias_parado': dias_parado,
        'manter': {'parado': dias_parado},
        'parados': produtos_parados(request.user, dias=dias_parado),
        'reposicao': previsao_de_reposicao(request.user),
    })
    return render(request, 'interfaces/relatorios_produtos.html', context)


@loja_required
def relatorios_clientes_view(request):
    inicio, fim, context = _base(request, 'clientes')
    dividas = idade_das_dividas(request.user)
    context.update({
        'dividas': dividas,
        'grafico_dividas': graficos.ranking(
            [f.rotulo for f in dividas.faixas], [f.total for f in dividas.faixas], 'A receber', cor='destaque',
        ),
        'grafico_fluxo': graficos.vendido_x_recebido(vendido_x_recebido(request.user, meses=12)),
        'melhores': melhores_clientes(request.user, inicio, fim),
        'sumidos': clientes_sumidos(request.user),
    })
    return render(request, 'interfaces/relatorios_clientes.html', context)


@loja_required
def relatorios_alteracoes_view(request):
    acao = request.GET.get('acao', '')
    if acao not in Acao.values:
        acao = ''
    registros = paginar(request, registros_do_usuario(request.user, acao))
    return render(request, 'interfaces/relatorios_alteracoes.html', {
        'aba': 'alteracoes',
        'registros': registros,
        'page_obj': registros,
        'acoes': Acao.choices,
        'acao': acao,
    })
