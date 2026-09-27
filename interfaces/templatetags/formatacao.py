from decimal import Decimal, InvalidOperation
from django import template
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
