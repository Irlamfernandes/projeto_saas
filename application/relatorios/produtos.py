"""Análises de produtos: lucro estimado, curva ABC, produtos parados e previsão de reposição."""
import math
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from django.db.models import DecimalField, ExpressionWrapper, F, Max, Q, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from application.relatorios.periodos import hoje_local, inicio_do_dia
from application.relatorios.selectors import filtrar_por_intervalo
from application.relatorios.vendas import DINHEIRO, RECEITA_DO_ITEM, ZERO, itens_do_usuario
from application.tenancy import filtrar_por_loja
from infrastructure.models import Produto

SEM_CATEGORIA = 'Sem categoria'
QUANTIDADE = DecimalField(max_digits=15, decimal_places=3)
LIMITE_CLASSE_A = Decimal('80')
LIMITE_CLASSE_B = Decimal('95')
CUSTO_DO_ITEM = ExpressionWrapper(F('quantidade') * F('custo_unitario'), output_field=DINHEIRO)


def percentual(parte, todo):
    if not todo:
        return ZERO
    return (Decimal(parte) * 100 / Decimal(todo)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------- lucro estimado

@dataclass(frozen=True)
class LinhaDeLucro:
    nome: str
    quantidade: Decimal
    receita: Decimal
    custo: Decimal
    sem_custo: bool = False

    @property
    def lucro(self):
        return self.receita - self.custo

    @property
    def margem(self):
        return percentual(self.lucro, self.receita)


@dataclass(frozen=True)
class RelatorioDeLucro:
    produtos: list
    categorias: list
    total: LinhaDeLucro
    produtos_sem_custo: int


def lucro_estimado(user, inicio=None, fim=None):
    """Receita menos custo, pelo preço de custo de cada produto no dia de cada venda."""
    itens = filtrar_por_intervalo(itens_do_usuario(user), inicio, fim, campo='venda__data_venda')
    agrupado = (
        itens.values('produto_id', 'produto__nome', 'produto__categoria')
        .annotate(unidades=Sum('quantidade'), receita=Sum(RECEITA_DO_ITEM), custo=Sum(CUSTO_DO_ITEM))
        .order_by()
    )
    produtos, por_categoria = [], defaultdict(list)
    for linha in agrupado:
        lucro = LinhaDeLucro(
            linha['produto__nome'], linha['unidades'], linha['receita'], linha['custo'],
            sem_custo=not linha['custo'],
        )
        produtos.append(lucro)
        por_categoria[linha['produto__categoria'] or SEM_CATEGORIA].append(lucro)

    produtos.sort(key=lambda l: l.lucro, reverse=True)
    categorias = sorted((_somar(nome, linhas) for nome, linhas in por_categoria.items()), key=lambda l: l.lucro, reverse=True)
    return RelatorioDeLucro(produtos, categorias, _somar('Total', produtos), sum(l.sem_custo for l in produtos))


def _somar(nome, linhas):
    return LinhaDeLucro(
        nome,
        sum(l.quantidade for l in linhas),
        sum((l.receita for l in linhas), ZERO),
        sum((l.custo for l in linhas), ZERO),
    )


# ---------------------------------------------------------------- curva ABC

@dataclass(frozen=True)
class LinhaABC:
    nome: str
    faturamento: Decimal
    participacao: Decimal
    acumulado: Decimal
    classe: str


@dataclass(frozen=True)
class ResumoDaClasse:
    classe: str
    produtos: int
    faturamento: Decimal
    participacao: Decimal


def curva_abc(user, inicio=None, fim=None):
    """Classe A: produtos que somam os primeiros 80% do faturamento; B: até 95%; C: o restante."""
    itens = filtrar_por_intervalo(itens_do_usuario(user), inicio, fim, campo='venda__data_venda')
    faturamentos = list(
        itens.values('produto_id', 'produto__nome').annotate(faturamento=Sum(RECEITA_DO_ITEM))
        .order_by('-faturamento', 'produto__nome')
    )
    total = sum((f['faturamento'] for f in faturamentos), ZERO)
    linhas, acumulado = [], ZERO
    for item in faturamentos:
        classe = _classe(percentual(acumulado, total))
        acumulado += item['faturamento']
        linhas.append(LinhaABC(
            item['produto__nome'], item['faturamento'], percentual(item['faturamento'], total),
            percentual(acumulado, total), classe,
        ))
    return linhas, [_resumo_da_classe(classe, linhas, total) for classe in 'ABC']


def _classe(acumulado_antes):
    """O produto que cruza o limite ainda pertence à classe (o 1º item é sempre A)."""
    if acumulado_antes < LIMITE_CLASSE_A:
        return 'A'
    if acumulado_antes < LIMITE_CLASSE_B:
        return 'B'
    return 'C'


def _resumo_da_classe(classe, linhas, total):
    da_classe = [l for l in linhas if l.classe == classe]
    faturamento = sum((l.faturamento for l in da_classe), ZERO)
    return ResumoDaClasse(classe, len(da_classe), faturamento, percentual(faturamento, total))


# ---------------------------------------------------------------- produtos parados

@dataclass(frozen=True)
class ProdutoParado:
    nome: str
    estoque: Decimal
    valor_em_estoque: Decimal
    ultima_venda: datetime | None
    dias_parado: int | None  # None: nunca vendeu
    unidade: str = 'un'


def produtos_parados(user, dias=60, agora=None):
    """Produtos com estoque que não vendem há `dias` dias ou mais (ou nunca venderam)."""
    agora = timezone.localtime(agora)
    limite = inicio_do_dia(agora.date() - timedelta(days=dias))
    produtos = (
        filtrar_por_loja(Produto.objects.filter(controla_estoque=True, quantidade_estoque__gt=0), user)
        .annotate(
            ultima_venda=Max('itemvenda__venda__data_venda'),
            valor_parado=ExpressionWrapper(F('quantidade_estoque') * F('preco_custo'), output_field=DINHEIRO),
        )
        .filter(Q(ultima_venda__lt=limite) | Q(ultima_venda__isnull=True))
        .order_by(F('ultima_venda').asc(nulls_first=True), 'nome')
    )
    return [
        ProdutoParado(
            p.nome, p.quantidade_estoque, p.valor_parado, p.ultima_venda,
            (agora - p.ultima_venda).days if p.ultima_venda else None, p.unidade,
        )
        for p in produtos
    ]


# ---------------------------------------------------------------- previsão de reposição

@dataclass(frozen=True)
class Reposicao:
    nome: str
    estoque: Decimal
    media_diaria: Decimal
    dias_restantes: int
    sugestao_de_compra: int
    unidade: str = 'un'


def previsao_de_reposicao(user, janela=30, horizonte=14, agora=None):
    """Produtos que acabam em até `horizonte` dias, pela média de vendas dos últimos `janela` dias.

    A sugestão de compra cobre `horizonte` dias de vendas. Produto sem controle de estoque não entra.
    """
    inicio = hoje_local(agora) - timedelta(days=janela - 1)
    vendidos = Coalesce(
        Sum('itemvenda__quantidade', filter=Q(itemvenda__venda__data_venda__date__gte=inicio)), Value(Decimal('0')),
        output_field=QUANTIDADE,
    )
    produtos = (
        filtrar_por_loja(Produto.objects.filter(controla_estoque=True), user)
        .annotate(vendido=vendidos).filter(vendido__gt=0)
    )
    previsoes = (_prever(p, Decimal(p.vendido) / janela, horizonte) for p in produtos)
    return sorted((p for p in previsoes if p.dias_restantes <= horizonte), key=lambda p: (p.dias_restantes, p.nome))


def _prever(produto, media_diaria, horizonte):
    dias_restantes = int(produto.quantidade_estoque / media_diaria)
    sugestao = max(0, math.ceil(media_diaria * horizonte - produto.quantidade_estoque))
    return Reposicao(
        produto.nome, produto.quantidade_estoque, media_diaria.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
        dias_restantes, sugestao, produto.unidade,
    )
