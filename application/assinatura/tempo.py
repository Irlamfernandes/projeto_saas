"""Soma do tempo de um plano ao vencimento."""
import calendar
from datetime import date, timedelta
from infrastructure.models import UnidadeDeTempo


def novo_vencimento(vencimento_atual, hoje, quantidade, unidade):
    """Soma a partir do maior entre hoje e o vencimento atual: quem renova antes de vencer não perde dias.

    Planos em dias somam dias; planos em meses somam meses de calendário (31/08 + 6 meses = 28/02).
    """
    base = max(vencimento_atual, hoje)
    if unidade == UnidadeDeTempo.MESES:
        return somar_meses(base, quantidade)
    return base + timedelta(days=quantidade)


def somar_meses(data, meses):
    """Mesmo dia `meses` depois; se o mês não tiver esse dia, o último dia dele."""
    indice = data.month - 1 + meses
    ano, mes = data.year + indice // 12, indice % 12 + 1
    return date(ano, mes, min(data.day, calendar.monthrange(ano, mes)[1]))
