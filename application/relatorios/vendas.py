"""Análises de vendas: faturamento no tempo, mais vendidos, horários e fluxo da caderneta."""
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from django.db.models import Count, DateField, DecimalField, ExpressionWrapper, F, Sum
from django.db.models.functions import ExtractHour, ExtractIsoWeekDay, TruncDate, TruncMonth
from application.relatorios.periodos import dias_entre, hoje_local, meses_ate
from application.relatorios.selectors import filtrar_por_intervalo
from application.tenancy import filtrar_por_loja
from infrastructure.models import ItemVenda, PagamentoCliente, Venda

ZERO = Decimal('0.00')
DINHEIRO = DecimalField(max_digits=14, decimal_places=2)
RECEITA_DO_ITEM = ExpressionWrapper(F('quantidade') * F('preco_unitario'), output_field=DINHEIRO)
DIAS_DA_SEMANA = ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom')  # ISO: 1 = segunda
HORARIO_PADRAO = (7, 20)


@dataclass(frozen=True)
class Ponto:
    data: date
    valor: Decimal


@dataclass(frozen=True)
class ProdutoVendido:
    nome: str
    quantidade: Decimal
    faturamento: Decimal
    unidade: str = 'un'


@dataclass(frozen=True)
class FluxoDoMes:
    mes: date
    vendido: Decimal
    recebido: Decimal


@dataclass(frozen=True)
class Celula:
    dia: str
    hora: int
    total: Decimal
    vendas: int
    intensidade: float  # 0 a 1, em relação à célula de maior total


@dataclass(frozen=True)
class MapaDeHorarios:
    dias: tuple
    linhas: list  # [(hora, [Celula x 7])]
    melhor: Celula | None


def vendas_do_usuario(user):
    return filtrar_por_loja(Venda.objects.all(), user)


def itens_do_usuario(user):
    return filtrar_por_loja(ItemVenda.objects.all(), user, campo='venda__loja')


def faturamento_por_dia(user, dias=30, agora=None):
    """Faturamento de cada um dos últimos `dias` dias (dias sem venda aparecem com zero)."""
    hoje = hoje_local(agora)
    inicio = hoje - timedelta(days=dias - 1)
    totais = _somar_por(vendas_do_usuario(user).filter(data_venda__date__gte=inicio), TruncDate('data_venda'), 'valor_total')
    return [Ponto(dia, totais.get(dia, ZERO)) for dia in dias_entre(inicio, hoje)]


def faturamento_por_mes(user, meses=12, agora=None):
    competencias = meses_ate(hoje_local(agora), meses)
    vendas = vendas_do_usuario(user).filter(data_venda__date__gte=competencias[0])
    totais = _somar_por(vendas, _mes('data_venda'), 'valor_total')
    return [Ponto(mes, totais.get(mes, ZERO)) for mes in competencias]


def vendido_x_recebido(user, meses=6, agora=None):
    """Por mês: quanto foi vendido NA CADERNETA (vendas com cliente) e quanto entrou de pagamento.

    Vendas de balcão (sem cliente) ficam de fora: não geram fiado, então compará-las com os
    pagamentos da caderneta distorceria a leitura.
    """
    competencias = meses_ate(hoje_local(agora), meses)
    na_caderneta = vendas_do_usuario(user).filter(cliente__isnull=False, data_venda__date__gte=competencias[0])
    vendido = _somar_por(na_caderneta, _mes('data_venda'), 'valor_total')
    pagamentos = filtrar_por_loja(PagamentoCliente.objects.filter(data_pagamento__date__gte=competencias[0]), user)
    recebido = _somar_por(pagamentos, _mes('data_pagamento'), 'valor')
    return [FluxoDoMes(mes, vendido.get(mes, ZERO), recebido.get(mes, ZERO)) for mes in competencias]


def mais_vendidos(user, inicio=None, fim=None, limite=10):
    itens = filtrar_por_intervalo(itens_do_usuario(user), inicio, fim, campo='venda__data_venda')
    linhas = (
        itens.values('produto_id', 'produto__nome', 'produto__unidade')
        .annotate(unidades=Sum('quantidade'), faturamento=Sum(RECEITA_DO_ITEM))
        .order_by('-unidades', 'produto__nome')[:limite]
    )
    return [ProdutoVendido(item['produto__nome'], item['unidades'], item['faturamento'], item['produto__unidade']) for item in linhas]


def mapa_de_horarios(user, dias=90, agora=None):
    """Total vendido por dia da semana e hora, nos últimos `dias` dias."""
    inicio = hoje_local(agora) - timedelta(days=dias - 1)
    agrupado = (
        vendas_do_usuario(user).filter(data_venda__date__gte=inicio)
        .annotate(dia=ExtractIsoWeekDay('data_venda'), hora=ExtractHour('data_venda'))
        .values('dia', 'hora').annotate(total=Sum('valor_total'), vendas=Count('id')).order_by()
    )
    celulas = {(g['dia'], g['hora']): (g['total'], g['vendas']) for g in agrupado}
    maximo = max((total for total, _ in celulas.values()), default=ZERO)
    horas = _faixa_de_horas(hora for _, hora in celulas)
    linhas = [(hora, [_celula(celulas, dia, hora, maximo) for dia in range(1, 8)]) for hora in horas]
    melhor = max((c for _, linha in linhas for c in linha if c.vendas), key=lambda c: c.total, default=None)
    return MapaDeHorarios(DIAS_DA_SEMANA, linhas, melhor)


def _celula(celulas, dia, hora, maximo):
    total, vendas = celulas.get((dia, hora), (ZERO, 0))
    intensidade = float(total / maximo) if maximo else 0.0
    return Celula(DIAS_DA_SEMANA[dia - 1], hora, total, vendas, intensidade)


def _faixa_de_horas(horas_com_venda):
    horas = list(horas_com_venda)
    primeira, ultima = (min(horas), max(horas)) if horas else HORARIO_PADRAO
    return range(primeira, ultima + 1)


def _mes(campo):
    return TruncMonth(campo, output_field=DateField())


def _somar_por(queryset, agrupador, campo_valor):
    linhas = queryset.annotate(chave=agrupador).values('chave').annotate(total=Sum(campo_valor)).order_by()
    return {linha['chave']: linha['total'] for linha in linhas}
