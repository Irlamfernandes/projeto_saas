"""Números do topo do painel, cada um comparado com o período equivalente anterior."""
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
from django.db.models import Q
from django.utils import timezone
from application.relatorios.clientes import idade_das_dividas
from application.relatorios.periodos import inicio_do_dia, mesmo_momento_no_mes_anterior
from application.relatorios.selectors import soma_das_vendas
from application.relatorios.vendas import vendas_do_usuario

DIAS_PARA_ALERTA_DE_DIVIDA = 60


@dataclass(frozen=True)
class Comparacao:
    atual: Decimal
    anterior: Decimal

    @property
    def variacao(self):
        """Variação percentual inteira; None quando não há base de comparação."""
        if not self.anterior:
            return None
        return round((self.atual - self.anterior) * 100 / self.anterior)

    @property
    def subiu(self):
        return (self.variacao or 0) >= 0

    @property
    def variacao_absoluta(self):
        return abs(self.variacao or 0)


@dataclass(frozen=True)
class Indicadores:
    hoje: Comparacao
    sete_dias: Comparacao
    mes: Comparacao
    a_receber: Decimal
    clientes_devendo: int
    devendo_ha_muito_tempo: int


def indicadores_do_painel(user, agora=None):
    """Hoje x mesmo dia da semana passada; 7 dias x 7 anteriores; mês até agora x mês anterior até o mesmo dia.

    Os períodos anteriores terminam no mesmo horário de agora, para a comparação ser justa.
    """
    agora = timezone.localtime(agora)
    inicio_hoje = inicio_do_dia(agora.date())
    inicio_mes = inicio_hoje.replace(day=1)
    semana = timedelta(days=7)
    intervalos = {
        'hoje': (inicio_hoje, agora),
        'hoje_antes': (inicio_hoje - semana, agora - semana),
        'sete': (inicio_hoje - timedelta(days=6), agora),
        'sete_antes': (inicio_hoje - timedelta(days=13), agora - semana),
        'mes': (inicio_mes, agora),
        'mes_antes': (mesmo_momento_no_mes_anterior(inicio_mes), mesmo_momento_no_mes_anterior(agora)),
    }
    somas = vendas_do_usuario(user).aggregate(**{
        nome: soma_das_vendas(Q(data_venda__gte=inicio, data_venda__lte=fim)) for nome, (inicio, fim) in intervalos.items()
    })
    dividas = idade_das_dividas(user, agora)
    return Indicadores(
        hoje=Comparacao(somas['hoje'], somas['hoje_antes']),
        sete_dias=Comparacao(somas['sete'], somas['sete_antes']),
        mes=Comparacao(somas['mes'], somas['mes_antes']),
        a_receber=dividas.total,
        clientes_devendo=len(dividas.devedores),
        devendo_ha_muito_tempo=dividas.acima_de(DIAS_PARA_ALERTA_DE_DIVIDA),
    )
