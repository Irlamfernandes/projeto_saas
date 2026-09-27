from decimal import Decimal, InvalidOperation
from django import template
from infrastructure.models.produto import Unidade, casas_decimais, sigla
from infrastructure.utils import formatacao
from infrastructure.utils.formatacao import moeda

register = template.Library()

register.filter('moeda', moeda)


@register.filter
def moeda_absoluta(valor):
    """Como `moeda`, sem sinal (ex.: exibir crédito do cliente como valor positivo)."""
    try:
        return moeda(abs(Decimal(str(valor or 0))))
    except (InvalidOperation, ValueError):
        return ''


@register.filter
def intensidade(fracao):
    """0..1 -> porcentagem de cor no mapa de calor (15% a 100%, para a menor venda ainda aparecer)."""
    return round(15 + 85 * float(fracao or 0))


@register.filter
def quantidade(valor, unidade):
    """{{ produto.quantidade_estoque|quantidade:produto.unidade }} -> '2,5 kg'."""
    return formatacao.quantidade(valor, unidade)


@register.filter
def descricao_do_item(item):
    """Item de venda: '2× Bolo' ou '0,35 kg Queijo'."""
    return formatacao.item(item.quantidade, item.produto.unidade, item.produto.nome)


@register.filter
def numero_simples(valor):
    """Valor para campo numérico do formulário, sem zeros sobrando: 2.500 -> '2.5'."""
    return f"{Decimal(str(valor or 0)).normalize():f}"


@register.filter
def passo_da_quantidade(casas):
    """Passo do campo de quantidade: 0 casas -> '1'; 3 casas -> '0.001'."""
    return f"{Decimal(1).scaleb(-int(casas or 0)):f}"


@register.simple_tag
def unidades_de_medida():
    return [
        {'valor': valor, 'rotulo': rotulo, 'sigla': sigla(valor), 'casas': casas_decimais(valor)}
        for valor, rotulo in Unidade.choices
    ]
