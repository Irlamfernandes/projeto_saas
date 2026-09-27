from decimal import Decimal, InvalidOperation
from django import template
from infrastructure.models.produto import MAXIMO_DE_OPCOES, Unidade, casas_decimais, sigla
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
    """Item de venda, compra ou perda: '2× Bolo', '0,35 kg Queijo', '1× Camiseta (G, Azul)'."""
    nome = formatacao.com_opcoes(item.produto.nome, getattr(item, 'opcoes', None))
    return formatacao.item(item.quantidade, item.produto.unidade, nome)


@register.filter
def numero_simples(valor):
    """Valor para campo numérico do formulário, sem zeros sobrando: 2.500 -> '2.5'."""
    return f"{Decimal(str(valor or 0)).normalize():f}"


@register.filter
def passo_da_quantidade(casas):
    """Passo do campo de quantidade: 0 casas -> '1'; 3 casas -> '0.001'."""
    return f"{Decimal(1).scaleb(-int(casas or 0)):f}"


@register.filter
def valores_da_opcao(opcao):
    """Valores de uma opção do produto como são digitados no cadastro: um por linha, 'G + 5,00' com acréscimo
    (sem separador de milhar, para ler de volta igual)."""
    return "\n".join(
        f"{valor['nome']} + {valor['acrescimo'].replace('.', ',')}" if Decimal(valor['acrescimo']) else valor['nome']
        for valor in opcao['valores']
    )


@register.simple_tag
def unidades_de_medida():
    return [
        {'valor': valor, 'rotulo': rotulo, 'sigla': sigla(valor), 'casas': casas_decimais(valor)}
        for valor, rotulo in Unidade.choices
    ]


@register.simple_tag
def maximo_de_opcoes():
    return MAXIMO_DE_OPCOES
