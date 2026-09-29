import calendar
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from django.db.models import Count, DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.functions import Coalesce
from application.relatorios.periodos import meses_ate
from application.tenancy import filtrar_por_loja
from infrastructure.models import Compra, Despesa, ItemVenda, Perda, Venda

ZERO = Decimal('0.00')
DINHEIRO = DecimalField(max_digits=14, decimal_places=2)
CATEGORIAS_SUGERIDAS = (
    'Aluguel', 'Luz', 'Água', 'Internet e telefone', 'Transporte', 'Embalagens', 'Taxas e maquininha',
    'Salários', 'Impostos', 'Manutenção', 'Propaganda',
)
MESES_NA_ESCOLHA = 12
# Itens vendidos e perdas valem pela quantidade × custo da época.
QUANTIDADE_X_CUSTO = ExpressionWrapper(F('quantidade') * F('custo_unitario'), output_field=DINHEIRO)


@dataclass(frozen=True)
class Mes:
    inicio: date
    fim: date

    @classmethod
    def de(cls, data):
        inicio = data.replace(day=1)
        return cls(inicio, inicio.replace(day=calendar.monthrange(inicio.year, inicio.month)[1]))

    @property
    def chave(self):
        return f"{self.inicio:%Y-%m}"


@dataclass(frozen=True)
class Resultado:
    """Resultado do mês: vendas − custo do que foi vendido − despesas − perdas.

    As compras não entram na conta: a mercadoria comprada vira custo quando é vendida (ou perda, se estragar).
    """
    vendas: Decimal
    custo_do_vendido: Decimal
    despesas: Decimal
    perdas: Decimal
    compras: Decimal
    itens_sem_custo: int

    @property
    def lucro_bruto(self):
        return self.vendas - self.custo_do_vendido

    @property
    def resultado(self):
        return self.lucro_bruto - self.despesas - self.perdas


def meses_para_escolher(hoje):
    return [Mes.de(inicio) for inicio in reversed(meses_ate(hoje, MESES_NA_ESCOLHA))]


def mes_escolhido(texto, hoje):
    """'2026-09' -> Mes; qualquer coisa fora dos meses oferecidos vira o mês atual."""
    meses = {mes.chave: mes for mes in meses_para_escolher(hoje)}
    return meses.get(texto, Mes.de(hoje))


def compras_do_mes(user, mes):
    compras = filtrar_por_loja(Compra.objects.prefetch_related('itens__produto'), user)
    return compras.filter(data__range=(mes.inicio, mes.fim))


def despesas_do_mes(user, mes):
    return filtrar_por_loja(Despesa.objects.all(), user).filter(data__range=(mes.inicio, mes.fim))


def perdas_do_mes(user, mes):
    perdas = filtrar_por_loja(Perda.objects.select_related('produto'), user)
    return perdas.filter(data__range=(mes.inicio, mes.fim))


def categorias_usadas(user):
    usadas = filtrar_por_loja(Despesa.objects.all(), user).values_list('categoria', flat=True).distinct()
    return sorted(set(CATEGORIAS_SUGERIDAS) | set(usadas), key=str.casefold)


def resultado_do_mes(user, mes):
    vendas = filtrar_por_loja(Venda.objects.all(), user).filter(data_venda__date__range=(mes.inicio, mes.fim))
    itens = filtrar_por_loja(ItemVenda.objects.all(), user, campo='venda__loja').filter(
        venda__data_venda__date__range=(mes.inicio, mes.fim),
    )
    vendido = itens.aggregate(custo=_soma(QUANTIDADE_X_CUSTO), sem_custo=Count('pk', filter=Q(custo_unitario=0)))
    return Resultado(
        vendas=_somar(vendas, F('valor_total')),
        custo_do_vendido=vendido['custo'].quantize(ZERO),
        despesas=_somar(despesas_do_mes(user, mes), F('valor')),
        perdas=_somar(perdas_do_mes(user, mes), QUANTIDADE_X_CUSTO).quantize(ZERO),
        compras=_somar(compras_do_mes(user, mes), F('valor_total')),
        itens_sem_custo=vendido['sem_custo'],
    )


def _soma(expressao):
    return Coalesce(Sum(expressao, output_field=DINHEIRO), ZERO, output_field=DINHEIRO)


def _somar(queryset, expressao):
    return queryset.aggregate(total=_soma(expressao))['total']
