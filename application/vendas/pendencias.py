"""Quanto falta pagar de cada compra do cliente.

A caderneta guarda só compras e pagamentos; o que está em aberto em cada compra é calculado:
1. o que o cliente pagou no ato fica com a própria venda (e o que passar do total vira crédito);
2. o resto da venda fica a prazo, dividido entre as parcelas (ou uma pendência "sem prazo" se não houver data);
3. os pagamentos feitos na caderneta quitam primeiro a compra mais antiga.
Por ser calculado, nada fica desatualizado quando uma venda é editada ou cancelada.
"""
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from django.utils import timezone

ZERO = Decimal('0.00')
CENTAVO = Decimal('0.01')


class Situacao:
    PAGA = 'paga'
    ATRASADA = 'atrasada'
    VENCE_HOJE = 'vence_hoje'
    A_VENCER = 'a_vencer'
    SEM_PRAZO = 'sem_prazo'


@dataclass(frozen=True)
class Pendencia:
    venda: object
    vencimento: date | None
    valor: Decimal
    pendente: Decimal

    def situacao(self, hoje=None):
        hoje = hoje or timezone.localdate()
        if self.pendente <= 0:
            return Situacao.PAGA
        if self.vencimento is None:
            return Situacao.SEM_PRAZO
        if self.vencimento < hoje:
            return Situacao.ATRASADA
        if self.vencimento == hoje:
            return Situacao.VENCE_HOJE
        return Situacao.A_VENCER


def dividir(total, partes):
    """Divide em partes iguais, em centavos; o que sobrar da divisão vai na última."""
    parte = (total / partes).quantize(CENTAVO, rounding=ROUND_DOWN)
    return [parte] * (partes - 1) + [total - parte * (partes - 1)]


def a_prazo(venda):
    """O que a venda deixou na caderneta: total menos o que foi pago no ato (negativo = crédito)."""
    return venda.valor_total - sum((pagamento.valor for pagamento in venda.pagamentos_no_ato.all()), ZERO)


def pendencias_da_venda(venda):
    """Partes a pagar da venda, antes de abater os pagamentos da caderneta."""
    restante = a_prazo(venda)
    if restante <= 0:
        return []
    vencimentos = [parcela.vencimento for parcela in venda.parcelas.all()] or [None]
    return [
        Pendencia(venda=venda, vencimento=vencimento, valor=valor, pendente=valor)
        for vencimento, valor in zip(vencimentos, dividir(restante, len(vencimentos)))
    ]


def abater(pendencias, credito):
    """Usa o crédito para quitar as pendências na ordem recebida (a mais antiga primeiro)."""
    resultado = []
    for pendencia in pendencias:
        usado = min(credito, pendencia.valor)
        credito -= usado
        resultado.append(Pendencia(pendencia.venda, pendencia.vencimento, pendencia.valor, pendencia.valor - usado))
    return resultado


def pendencias_do_cliente(cliente):
    """Todas as partes das compras do cliente, da mais antiga para a mais nova, com o que ainda falta de cada uma."""
    vendas = cliente.vendas.prefetch_related('parcelas', 'pagamentos_no_ato').order_by('data_venda', 'pk')
    pagos_na_caderneta = sum((p.valor for p in cliente.pagamentos.all() if p.venda_id is None), ZERO)
    sobras_do_ato = sum((-a_prazo(venda) for venda in vendas if a_prazo(venda) < 0), ZERO)
    pendencias = [pendencia for venda in vendas for pendencia in pendencias_da_venda(venda)]
    return abater(pendencias, pagos_na_caderneta + sobras_do_ato)
