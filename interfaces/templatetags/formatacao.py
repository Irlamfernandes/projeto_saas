from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from django import template

register = template.Library()

_CENTAVOS = Decimal('0.01')


@register.filter
def moeda(valor):
    """Valor com 2 casas no formato pt-BR (1234,50). Equivale a `|default:0|floatformat:2`,
    mas sem a maquinaria de localização do floatformat, que pesa em listas longas."""
    try:
        numero = Decimal(str(valor or 0)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return ''
    return f"{numero + 0:f}".replace('.', ',')


@register.filter
def moeda_absoluta(valor):
    """Como `moeda`, sem sinal (ex.: exibir crédito do cliente como valor positivo)."""
    try:
        return moeda(abs(Decimal(str(valor or 0))))
    except (InvalidOperation, ValueError):
        return ''
