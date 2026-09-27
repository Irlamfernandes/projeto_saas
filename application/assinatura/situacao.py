"""Situação do plano da loja: quantos dias faltam, se venceu e qual aviso mostrar.

O vencimento vale até o fim do dia: vencer em 26/10 significa usar tudo em 26/10; a trava começa em 27/10.
"""
from dataclasses import dataclass
from datetime import date
from django.utils import timezone

DIAS_DE_AVISO = 7  # os avisos começam uma semana antes


@dataclass(frozen=True)
class SituacaoDoPlano:
    vencimento: date
    dias_restantes: int

    @property
    def vencido(self):
        return self.dias_restantes < 0

    @property
    def nivel(self):
        """'critico', 'alerta', 'info' ou '' (sem aviso): o tom sobe conforme o vencimento chega."""
        if self.dias_restantes <= 1:
            return 'critico'
        if self.dias_restantes <= 3:
            return 'alerta'
        if self.dias_restantes <= DIAS_DE_AVISO:
            return 'info'
        return ''

    @property
    def aviso(self):
        data = self.vencimento.strftime('%d/%m/%Y')
        if self.vencido:
            return (f"Seu plano venceu em {data}. Você ainda pode consultar tudo, "
                    "mas para registrar vendas e fazer alterações é preciso renovar.")
        if self.dias_restantes == 0:
            return "Seu plano vence hoje. Renove para continuar usando o sistema por completo."
        if self.dias_restantes == 1:
            return f"Seu plano vence amanhã ({data}). Renove para não ter o uso limitado."
        if self.nivel:
            return f"Seu plano vence em {self.dias_restantes} dias ({data}). Renove para não ter o uso limitado."
        return ''


def situacao_do_plano(loja, hoje=None):
    """None para quem não tem loja (superusuário): não há plano a mostrar nem a travar."""
    if loja is None:
        return None
    hoje = hoje or timezone.localdate()
    return SituacaoDoPlano(vencimento=loja.vencimento, dias_restantes=(loja.vencimento - hoje).days)


def plano_vencido(user):
    if user.is_superuser:
        return False
    situacao = situacao_do_plano(user.loja)
    return situacao is not None and situacao.vencido
