"""Dinheiro que entrou, por forma de pagamento (dinheiro, Pix, cartões...)."""
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from django.db.models import Sum
from application.relatorios.produtos import percentual
from application.relatorios.selectors import filtrar_por_intervalo
from application.tenancy import filtrar_por_loja
from infrastructure.models import FormaDePagamento, PagamentoCliente, Venda

NAO_INFORMADA = 'Não informada'


@dataclass(frozen=True)
class LinhaDeForma:
    forma: str
    valor: Decimal
    participacao: Decimal


def recebido_por_forma(user, inicio=None, fim=None):
    """Balcão entra pelo total da venda (pago na hora); caderneta, pelos pagamentos — inclusive os feitos
    no ato de uma venda com cliente. Assim cada real recebido conta uma vez só."""
    balcao = filtrar_por_intervalo(
        filtrar_por_loja(Venda.objects.filter(cliente__isnull=True), user), inicio, fim,
    ).values('forma_pagamento').annotate(total=Sum('valor_total')).order_by()
    caderneta = filtrar_por_intervalo(
        filtrar_por_loja(PagamentoCliente.objects.all(), user), inicio, fim, campo='data_pagamento',
    ).values('forma_pagamento').annotate(total=Sum('valor')).order_by()

    somas = Counter()
    for linha in (*balcao, *caderneta):
        somas[linha['forma_pagamento']] += linha['total']

    total = sum(somas.values(), Decimal('0'))
    ordem = sorted(somas.items(), key=lambda par: (-par[1], _rotulo(par[0])))  # maior valor primeiro; empate: A–Z
    linhas = [LinhaDeForma(_rotulo(forma), valor, percentual(valor, total)) for forma, valor in ordem]
    return linhas, total


def _rotulo(forma):
    return FormaDePagamento(forma).label if forma else NAO_INFORMADA
