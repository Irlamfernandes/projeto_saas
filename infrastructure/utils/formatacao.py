"""Formatação de valores em reais e de quantidades, usada nas telas e nos textos gerados pelas regras de negócio."""
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from infrastructure.models.produto import Unidade, sigla

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


def numero(valor):
    """Quantidade sem zeros sobrando, no formato pt-BR: 2.500 -> '2,5'; 3.000 -> '3'; 1234.5 -> '1.234,5'."""
    try:
        numero = Decimal(str(valor or 0)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP).normalize()
    except (InvalidOperation, ValueError):
        return ''
    return f"{numero + 0:,f}".replace(',', '_').replace('.', ',').replace('_', '.')


def quantidade(valor, unidade):
    """'2,5 kg', '3 un.'."""
    return f"{numero(valor)} {sigla(unidade)}"


def item(valor, unidade, nome):
    """Item de venda em texto: '2× Bolo' (por unidade) ou '0,35 kg Queijo'."""
    if unidade in (Unidade.UNIDADE, '', None):
        return f"{numero(valor)}× {nome}"
    return f"{numero(valor)} {sigla(unidade)} {nome}"


def com_opcoes(nome, opcoes):
    """Nome do produto com o que foi escolhido nas opções: 'Camiseta (G, Azul)'."""
    valores = ", ".join(opcao['valor'] for opcao in opcoes or ())
    return f"{nome} ({valores})" if valores else nome
