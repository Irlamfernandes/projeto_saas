import calendar
from datetime import datetime, time, timedelta
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


def hoje_local(agora=None):
    return timezone.localtime(agora).date()


def inicio_do_dia(data):
    """Meia-noite local da data, como datetime com fuso."""
    return timezone.make_aware(datetime.combine(data, time.min))


def dias_entre(inicio, fim):
    """Datas de `inicio` a `fim`, inclusive."""
    return [inicio + timedelta(days=i) for i in range((fim - inicio).days + 1)]


def primeiro_dia_do_mes(data, meses_atras=0):
    ano, mes = divmod(data.year * 12 + data.month - 1 - meses_atras, 12)
    return data.replace(year=ano, month=mes + 1, day=1)


def meses_ate(data, quantidade):
    """Primeiro dia de cada um dos últimos `quantidade` meses, terminando no mês de `data`."""
    return [primeiro_dia_do_mes(data, n) for n in range(quantidade - 1, -1, -1)]


def mesmo_momento_no_mes_anterior(momento):
    """Mesmo dia e hora do mês anterior; dia ajustado quando o mês anterior é mais curto."""
    inicio_anterior = primeiro_dia_do_mes(momento.date(), 1)
    ultimo_dia = calendar.monthrange(inicio_anterior.year, inicio_anterior.month)[1]
    return momento.replace(year=inicio_anterior.year, month=inicio_anterior.month, day=min(momento.day, ultimo_dia))
