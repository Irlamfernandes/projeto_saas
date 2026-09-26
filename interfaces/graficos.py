"""Converte resultados das análises no formato lido por static/js/graficos.js (via |json_script)."""
from django.utils.formats import date_format


def _frase(texto):
    """Maiúscula só no início: o locale pt-BR do Django capitaliza os meses ("20 de Março")."""
    return texto[:1].upper() + texto[1:].lower()


def data_por_extenso(data):
    """Ex.: 'Sexta-feira, 20 de março'."""
    return _frase(date_format(data, r'l, j \d\e F'))


def _serie(nome, valores, cor='marca'):
    return {'nome': nome, 'valores': [float(v) for v in valores], 'cor': cor}


def diario(pontos, nome='Faturamento'):
    return {
        'rotulos': [date_format(p.data, 'd/m') for p in pontos],
        'detalhes': [data_por_extenso(p.data) for p in pontos],
        'series': [_serie(nome, (p.valor for p in pontos))],
    }


def mensal(pontos, nome='Faturamento'):
    return {
        'rotulos': [date_format(p.data, 'b/y') for p in pontos],
        'detalhes': [_frase(date_format(p.data, r'F \d\e Y')) for p in pontos],
        'series': [_serie(nome, (p.valor for p in pontos))],
    }


def vendido_x_recebido(fluxo):
    return {
        'rotulos': [date_format(f.mes, 'b/y') for f in fluxo],
        'detalhes': [_frase(date_format(f.mes, r'F \d\e Y')) for f in fluxo],
        'series': [
            _serie('Vendido na caderneta', (f.vendido for f in fluxo)),
            _serie('Recebido', (f.recebido for f in fluxo), cor='destaque'),
        ],
    }


def ranking(rotulos, valores, nome, cor='marca'):
    return {'rotulos': list(rotulos), 'series': [_serie(nome, valores, cor)]}
