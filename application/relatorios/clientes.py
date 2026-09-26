"""Análises de clientes: idade das dívidas da caderneta, melhores clientes e clientes sumidos."""
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Count, Max, Min, Q, Sum
from django.utils import timezone
from application.relatorios.periodos import inicio_do_dia
from application.relatorios.vendas import ZERO
from application.tenancy import filtrar_por_loja
from infrastructure.models import Cliente

FAIXAS_DE_ATRASO = (
    ('Até 30 dias', 0, 30),
    ('31 a 60 dias', 31, 60),
    ('61 a 90 dias', 61, 90),
    ('Mais de 90 dias', 91, None),
)


@dataclass(frozen=True)
class Devedor:
    cliente: Cliente
    saldo: Decimal
    dias_sem_pagar: int


@dataclass(frozen=True)
class FaixaDeAtraso:
    rotulo: str
    clientes: int
    total: Decimal


@dataclass(frozen=True)
class IdadeDasDividas:
    faixas: list
    devedores: list
    total: Decimal

    def acima_de(self, dias):
        return sum(1 for d in self.devedores if d.dias_sem_pagar > dias)


def idade_das_dividas(user, agora=None):
    """Clientes devendo, agrupados por dias desde o último pagamento (ou desde a 1ª compra, se nunca pagou)."""
    agora = timezone.localtime(agora)
    clientes = (
        filtrar_por_loja(Cliente.objects.com_saldo(), user)
        .filter(saldo_calculado__gt=0)
        .annotate(ultimo_pagamento=Max('pagamentos__data_pagamento'), primeira_compra=Min('vendas__data_venda'))
    )
    devedores = sorted(
        (Devedor(c, c.saldo_calculado, _dias_sem_pagar(c, agora)) for c in clientes),
        key=lambda d: (-d.dias_sem_pagar, -d.saldo),
    )
    faixas = [_faixa(rotulo, minimo, maximo, devedores) for rotulo, minimo, maximo in FAIXAS_DE_ATRASO]
    return IdadeDasDividas(faixas, devedores, sum((d.saldo for d in devedores), ZERO))


def _dias_sem_pagar(cliente, agora):
    referencia = cliente.ultimo_pagamento or cliente.primeira_compra or agora
    return max(0, (agora - referencia).days)


def _faixa(rotulo, minimo, maximo, devedores):
    na_faixa = [d for d in devedores if d.dias_sem_pagar >= minimo and (maximo is None or d.dias_sem_pagar <= maximo)]
    return FaixaDeAtraso(rotulo, len(na_faixa), sum((d.saldo for d in na_faixa), ZERO))


@dataclass(frozen=True)
class ClienteRanqueado:
    cliente: Cliente
    total: Decimal
    compras: int
    ultima_compra: datetime | None = None
    dias_sem_comprar: int | None = None


def melhores_clientes(user, inicio=None, fim=None, limite=10):
    """Quem mais comprou (em reais) no período."""
    no_periodo = Q()
    if inicio:
        no_periodo &= Q(vendas__data_venda__date__gte=inicio)
    if fim:
        no_periodo &= Q(vendas__data_venda__date__lte=fim)
    clientes = (
        filtrar_por_loja(Cliente.objects.all(), user)
        .annotate(total=Sum('vendas__valor_total', filter=no_periodo), compras=Count('vendas', filter=no_periodo))
        .filter(total__gt=0)
        .order_by('-total', 'nome')[:limite]
    )
    return [ClienteRanqueado(c, c.total, c.compras) for c in clientes]


def clientes_sumidos(user, dias=60, agora=None, limite=20):
    """Clientes que já compraram, mas não compram há mais de `dias` dias (os que mais gastavam primeiro)."""
    agora = timezone.localtime(agora)
    limite_data = inicio_do_dia(agora.date() - timedelta(days=dias))
    clientes = (
        filtrar_por_loja(Cliente.objects.all(), user)
        .annotate(ultima_compra=Max('vendas__data_venda'), total=Sum('vendas__valor_total'), compras=Count('vendas'))
        .filter(ultima_compra__lt=limite_data)
        .order_by('-total', 'nome')[:limite]
    )
    return [
        ClienteRanqueado(c, c.total, c.compras, c.ultima_compra, (agora - c.ultima_compra).days)
        for c in clientes
    ]
