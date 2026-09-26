from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from django import template

register = template.Library()

_CENTAVOS = Decimal('0.01')


@register.filter
def moeda(valor):
    """Valor em reais no formato pt-BR, com separador de milhar: 1234.5 -> '1.234,50'.

    Arredonda como o `floatformat` (meio para cima), mas sem a maquinaria de localização dele,
    que pesa em listas longas.
    """
    try:
        numero = Decimal(str(valor or 0)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return ''
    return f"{numero + 0:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


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
