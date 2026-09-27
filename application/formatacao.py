"""Formatação de valores em reais, usada nas telas e nos textos gerados pelas regras de negócio."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CENTAVOS = Decimal('0.01')


def moeda(valor):
    """Valor em reais no formato pt-BR, com separador de milhar: 1234.5 -> '1.234,50' ('' se inválido).

    Arredonda como o `floatformat` (meio para cima), mas sem a maquinaria de localização dele,
    que pesa em listas longas.
    """
    try:
        numero = Decimal(str(valor or 0)).quantize(_CENTAVOS, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        return ''
    return f"{numero + 0:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')


def reais(valor):
    """'R$ 1.234,50'."""
    return f"R$ {moeda(valor)}"
