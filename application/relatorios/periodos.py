from datetime import timedelta
from django.utils import timezone


def inicios_dos_periodos(agora=None):
    """Início de cada período de faturamento, sempre no fuso local da loja (não em UTC)."""
    hoje = timezone.localtime(agora).replace(hour=0, minute=0, second=0, microsecond=0)
    return {
        'hoje': hoje,
        'semana': hoje - timedelta(days=6),
        'quinzena': hoje - timedelta(days=14),
        'mes': hoje.replace(day=1),
        'bimestre': hoje - timedelta(days=59),
        'trimestre': hoje - timedelta(days=89),
        'ano': hoje.replace(month=1, day=1),
    }
