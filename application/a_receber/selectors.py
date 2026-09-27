"""Quem cobrar: clientes com parte de compra atrasada, vencendo hoje ou nos próximos dias.

Compras sem prazo não entram: não há data combinada para lembrar.
"""
from dataclasses import dataclass
from datetime import date, timedelta
from application.tenancy import filtrar_por_loja
from application.vendas.pendencias import ZERO, Situacao, dados_para_pendencias, pendencias_do_cliente
from infrastructure.models import Cliente, LembreteDePagamento

DIAS_DE_ANTECEDENCIA = 7
ORDEM_DE_GRAVIDADE = (Situacao.ATRASADA, Situacao.VENCE_HOJE, Situacao.A_VENCER)


@dataclass(frozen=True)
class ClienteACobrar:
    cliente: Cliente
    pendencias: tuple  # só as que vencem até o limite, da mais antiga para a mais nova
    hoje: date
    lembrado_hoje: bool = False

    @property
    def total(self):
        return sum((pendencia.pendente for pendencia in self.pendencias), ZERO)

    @property
    def atrasado(self):
        return sum((p.pendente for p in self.pendencias if p.situacao(self.hoje) == Situacao.ATRASADA), ZERO)

    @property
    def situacao(self):
        """A mais grave entre as partes: atrasada > vence hoje > a vencer."""
        situacoes = {pendencia.situacao(self.hoje) for pendencia in self.pendencias}
        return next(situacao for situacao in ORDEM_DE_GRAVIDADE if situacao in situacoes)

    @property
    def primeiro_vencimento(self):
        return min(pendencia.vencimento for pendencia in self.pendencias)


def clientes_a_cobrar(user, hoje, dias=DIAS_DE_ANTECEDENCIA):
    """Do vencimento mais antigo para o mais novo. Só olha quem deve algo (saldo positivo)."""
    devendo = (
        filtrar_por_loja(Cliente.objects.select_related('loja'), user).com_saldo().filter(saldo_calculado__gt=0)
        .prefetch_related(*dados_para_pendencias())
    )
    lembrados = set(
        filtrar_por_loja(LembreteDePagamento.objects.all(), user)
        .filter(enviado_em__date=hoje).values_list('cliente_id', flat=True)
    )
    a_cobrar = [cobranca_do_cliente(cliente, hoje, dias, cliente.pk in lembrados) for cliente in devendo]
    return sorted(filter(None, a_cobrar), key=lambda item: (item.primeiro_vencimento, item.cliente.nome))


def cobranca_do_cliente(cliente, hoje, dias=DIAS_DE_ANTECEDENCIA, lembrado_hoje=False):
    """O que cobrar deste cliente agora; None se nada dele vence até o limite."""
    limite = hoje + timedelta(days=dias)
    vencendo = tuple(
        pendencia for pendencia in pendencias_do_cliente(cliente)
        if pendencia.pendente > 0 and pendencia.vencimento and pendencia.vencimento <= limite
    )
    return ClienteACobrar(cliente, vencendo, hoje, lembrado_hoje) if vencendo else None
