"""Retrato de um PDF do reportlab: o conteúdo montado (parágrafos, espaços, tabelas, imagens) como dados comparáveis.

Os testes comparam o retrato com um arquivo JSON guardado em infrastructure/tests/retratos/. Mudou o layout de
propósito? Gere de novo com RETRATO_ATUALIZAR=1 e confira a diferença no git antes de commitar.
"""
import json
import os
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from reportlab.lib.colors import Color
from reportlab.platypus import Image, Paragraph, Spacer, Table

PASTA = Path(__file__).resolve().parent.parent / 'infrastructure' / 'tests' / 'retratos'
ATRIBUTOS_DO_ESTILO = ('name', 'fontName', 'fontSize', 'leading', 'textColor', 'spaceBefore', 'spaceAfter', 'alignment')


def _simples(valor):
    if isinstance(valor, Color):
        return valor.hexval()
    if isinstance(valor, (list, tuple)):
        return [_simples(item) for item in valor]
    return valor


def _estilo(estilo):
    return {
        **{nome: _simples(getattr(estilo, nome)) for nome in ATRIBUTOS_DO_ESTILO},
        'parent': getattr(estilo.parent, 'name', None),
    }


def retrato(item):
    if isinstance(item, list):
        return [retrato(parte) for parte in item]
    if isinstance(item, Paragraph):
        return {'paragrafo': item.text, 'estilo': _estilo(item.style)}
    if isinstance(item, Spacer):
        return {'espaco': [item.width, item.height]}
    if isinstance(item, Image):
        return {'imagem': [round(item.drawWidth, 3), round(item.drawHeight, 3)]}
    if isinstance(item, Table):
        return {
            'tabela': [[retrato(celula) for celula in linha] for linha in item._cellvalues],
            'larguras': _simples(item._argW),
            'alinhamento': item.hAlign,
            'estilo': [_simples(comando) for comando in getattr(item, 'comandos_do_retrato', [])],
        }
    return item


@contextmanager
def capturando_documento(modulo):
    """Troca o SimpleDocTemplate de `modulo` e guarda os estilos aplicados nas tabelas. Devolve um dict que recebe
    'documento' (os argumentos do SimpleDocTemplate) e 'conteudo' (o retrato do que foi para o build)."""
    capturado = {}
    original = Table.setStyle

    def guardar_estilo(tabela, estilo):
        tabela.comandos_do_retrato = [*getattr(tabela, 'comandos_do_retrato', []), *estilo.getCommands()]
        return original(tabela, estilo)

    with patch.object(Table, 'setStyle', guardar_estilo), patch.object(modulo, 'SimpleDocTemplate') as documento:
        yield capturado
    argumentos = documento.call_args
    capturado['documento'] = {**{chave: _simples(valor) for chave, valor in argumentos.kwargs.items()}}
    capturado['conteudo'] = retrato(documento.return_value.build.call_args.args[0])


def conferir(teste, nome, atual):
    """Compara `atual` com o retrato guardado (ou grava, com RETRATO_ATUALIZAR=1)."""
    arquivo = PASTA / f'{nome}.json'
    atual = json.loads(json.dumps(atual, ensure_ascii=False))
    if os.environ.get('RETRATO_ATUALIZAR') == '1':
        arquivo.write_text(json.dumps(atual, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    teste.maxDiff = None
    teste.assertEqual(atual, json.loads(arquivo.read_text(encoding='utf-8')))
