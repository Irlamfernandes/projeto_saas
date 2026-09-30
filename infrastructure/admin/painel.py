"""Painel inicial do admin: situação das lojas e das assinaturas, com gráficos.

Só o superusuário (dono do sistema) vê os números de todas as lojas; os demais veem só o menu.
"""
import json
from dataclasses import dataclass
from datetime import date, timedelta
from django.db.models import Count, Exists, OuterRef, Sum
from django.db.models.functions import TruncMonth
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from infrastructure.models import Cobranca, ErroDoSistema, LojaModel, StatusDaCobranca
from infrastructure.utils.formatacao import reais

MESES_NOS_GRAFICOS = 6
DIAS_PARA_AVISAR = 7
ULTIMAS_COBRANCAS = 5
NOMES_DOS_MESES = ('jan', 'fev', 'mar', 'abr', 'mai', 'jun', 'jul', 'ago', 'set', 'out', 'nov', 'dez')
COR_PRINCIPAL = 'var(--color-primary-600)'
COR_ALERTA = '#c96a05'
COR_CRITICA = '#d03b3b'


@dataclass(frozen=True)
class Cartao:
    titulo: str
    valor: str
    detalhe: str
    link: str


def painel_do_admin(request, context):
    if not request.user.is_superuser:
        return context
    hoje = timezone.localdate()
    ativas = LojaModel.objects.filter(ativo=True)
    return {
        **context,
        'painel': {
            'erros': erros_em_aberto(),
            'cartoes': cartoes(ativas, hoje),
            'grafico_recebido': json.dumps(grafico_recebido_por_mes(hoje)),
            'grafico_lojas_novas': json.dumps(grafico_lojas_novas_por_mes(hoje)),
            'grafico_situacao': json.dumps(grafico_situacao_dos_planos(ativas, hoje)),
            'vencendo': tabela_vencendo(ativas, hoje),
            'ultimas_cobrancas': tabela_ultimas_cobrancas(),
        },
    }


def erros_em_aberto():
    """Aviso no topo do painel quando alguma tela quebrou em produção (tela "Erros do sistema")."""
    link = reverse('admin:infrastructure_errodosistema_changelist')
    return {'quantidade': ErroDoSistema.objects.filter(resolvido=False).count(), 'link': f"{link}?resolvido__exact=0"}


def cartoes(ativas, hoje):
    lojas = reverse('admin:infrastructure_lojamodel_changelist')
    pagas = Cobranca.objects.filter(status=StatusDaCobranca.PAGA)
    recebido = pagas.filter(paga_em__date__gte=hoje.replace(day=1)).aggregate(total=Sum('valor'))['total']
    em_teste = ativas.exclude(Exists(pagas.filter(loja=OuterRef('pk')))).count()
    return [
        Cartao("Lojas ativas", str(ativas.count()), f"{em_teste} em teste grátis", f"{lojas}?ativo__exact=1"),
        Cartao("Vencem em até 7 dias", str(_vencendo(ativas, hoje).count()), "Hora de lembrar de renovar", lojas),
        Cartao("Planos vencidos", str(ativas.filter(vencimento__lt=hoje).count()), "Em modo só consulta", lojas),
        Cartao("Recebido no mês", reais(recebido or 0), "Planos pagos por Pix",
               reverse('admin:infrastructure_cobranca_changelist')),
    ]


def grafico_recebido_por_mes(hoje):
    meses = _ultimos_meses(hoje)
    por_mes = _somar_por_mes(
        Cobranca.objects.filter(status=StatusDaCobranca.PAGA, paga_em__date__gte=meses[0]),
        'paga_em', Sum('valor'),
    )
    return _barras(meses, [float(por_mes.get(mes, 0)) for mes in meses], "Recebido (R$)", COR_PRINCIPAL)


def grafico_lojas_novas_por_mes(hoje):
    meses = _ultimos_meses(hoje)
    por_mes = _somar_por_mes(LojaModel.objects.filter(criado_em__date__gte=meses[0]), 'criado_em', Count('pk'))
    return _barras(meses, [por_mes.get(mes, 0) for mes in meses], "Lojas novas", COR_PRINCIPAL)


def grafico_situacao_dos_planos(ativas, hoje):
    vencendo = _vencendo(ativas, hoje).count()
    vencidas = ativas.filter(vencimento__lt=hoje).count()
    em_dia = ativas.count() - vencendo - vencidas
    return {
        'labels': ["Em dia", "Vencendo", "Vencidas"],
        'datasets': [{
            'label': "Lojas", 'data': [em_dia, vencendo, vencidas],
            'backgroundColor': [COR_PRINCIPAL, COR_ALERTA, COR_CRITICA],
        }],
    }


def tabela_vencendo(ativas, hoje):
    linhas = [
        [_link_da_loja(loja), loja.vencimento.strftime('%d/%m/%Y'), _dias(loja.vencimento, hoje)]
        for loja in _vencendo(ativas, hoje).order_by('vencimento')[:10]
    ]
    return {'headers': ["Loja", "Vencimento", "Faltam"], 'rows': linhas}


def tabela_ultimas_cobrancas():
    cobrancas = Cobranca.objects.select_related('loja')[:ULTIMAS_COBRANCAS]
    linhas = [
        [timezone.localtime(c.criada_em).strftime('%d/%m %H:%M'), c.loja.nome_loja, c.plano_nome, reais(c.valor),
         c.get_status_display()]
        for c in cobrancas
    ]
    return {'headers': ["Data", "Loja", "Plano", "Valor", "Situação"], 'rows': linhas}


def _vencendo(ativas, hoje):
    return ativas.filter(vencimento__gte=hoje, vencimento__lte=hoje + timedelta(days=DIAS_PARA_AVISAR))


def _dias(vencimento, hoje):
    dias = (vencimento - hoje).days
    return {0: "vence hoje", 1: "1 dia"}.get(dias, f"{dias} dias")


def _link_da_loja(loja):
    return format_html('<a href="{}" class="text-primary-600 font-semibold">{}</a>',
                       reverse('admin:infrastructure_lojamodel_change', args=[loja.pk]), loja.nome_loja)


def _ultimos_meses(hoje):
    """Primeiro dia de cada um dos últimos meses, do mais antigo ao atual."""
    meses = []
    ano, mes = hoje.year, hoje.month
    for _ in range(MESES_NOS_GRAFICOS):
        meses.append(date(ano, mes, 1))
        ano, mes = (ano - 1, 12) if mes == 1 else (ano, mes - 1)
    return list(reversed(meses))


def _somar_por_mes(queryset, campo_de_data, agregado):
    linhas = (
        queryset.annotate(mes=TruncMonth(campo_de_data, tzinfo=timezone.get_current_timezone()))
        .values('mes').annotate(total=agregado).values_list('mes', 'total')
    )
    return {mes.date() if hasattr(mes, 'date') else mes: total for mes, total in linhas}


def _barras(meses, valores, rotulo, cor):
    return {
        'labels': [f"{NOMES_DOS_MESES[m.month - 1]}/{m.year % 100:02d}" for m in meses],
        'datasets': [{'label': rotulo, 'data': valores, 'backgroundColor': cor}],
    }
