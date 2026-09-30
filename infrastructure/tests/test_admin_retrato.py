"""Retrato da configuração do admin: colunas, filtros, buscas, formulários, ações, rótulos e menu.

Qualquer mudança nessas telas aparece aqui como diferença. Mudou de propósito? Gere o retrato de novo:
    RETRATO_ATUALIZAR=1 python -m pytest infrastructure/tests/test_admin_retrato.py
e confira a diferença do arquivo no git antes de commitar.
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace
from django.contrib import admin
from django.test import SimpleTestCase
from infrastructure.admin import tema

RETRATO = Path(__file__).with_name('retratos') / 'admin.json'
ATRIBUTOS = (
    'list_display', 'list_display_links', 'list_filter', 'list_editable', 'search_fields', 'list_select_related',
    'date_hierarchy', 'ordering', 'list_per_page', 'exclude', 'fields', 'readonly_fields', 'fieldsets', 'add_fieldsets',
    'filter_horizontal', 'autocomplete_fields', 'raw_id_fields', 'actions', 'actions_list', 'actions_row',
    'actions_detail', 'actions_submit_line', 'inlines', 'change_form_template', 'change_list_template',
    'change_form_outer_after_template',
)
DETALHES_DAS_FUNCOES = (
    'short_description', 'admin_order_field', 'boolean', 'label', 'header', 'dropdown', 'url_path', 'icon', 'attrs',
    'allowed_permissions', 'image',
)


def _simples(valor):
    """Deixa o valor comparável em JSON: tuplas viram listas, classes e funções viram nomes, textos traduzíveis viram str."""
    if isinstance(valor, dict):
        return {str(chave): _simples(item) for chave, item in valor.items()}
    if isinstance(valor, (list, tuple, set, frozenset)):
        return [_simples(item) for item in valor]
    if isinstance(valor, (bool, int, float)) or valor is None:
        return valor
    if isinstance(valor, type) or callable(valor):
        return getattr(valor, '__name__', repr(valor))
    return str(valor)


def _funcoes_citadas(modelo_admin, valores):
    nomes = [nome for nome in valores if isinstance(nome, str) and callable(getattr(modelo_admin, nome, None))]
    return {
        nome: {chave: _simples(getattr(getattr(modelo_admin, nome), chave)) for chave in DETALHES_DAS_FUNCOES
               if hasattr(getattr(modelo_admin, nome), chave)}
        for nome in nomes
    }


def _retrato_do_admin(modelo_admin):
    atributos = {nome: _simples(getattr(modelo_admin, nome, None)) for nome in ATRIBUTOS}
    campos_dos_grupos = [campo for _titulo, opcoes in (modelo_admin.fieldsets or ()) for campo in opcoes['fields']]
    citados = [
        *(modelo_admin.list_display or ()), *(modelo_admin.readonly_fields or ()), *(modelo_admin.actions or ()),
        *(modelo_admin.fields or ()), *campos_dos_grupos,
        *(getattr(modelo_admin, nome, None) or () for nome in ('actions_list', 'actions_row', 'actions_detail'))
    ]
    planos = [item for item in citados if isinstance(item, str)] + [
        nome for grupo in citados if isinstance(grupo, (list, tuple)) for nome in grupo
    ]
    filtros_proprios = {
        filtro.__name__: {'title': str(filtro.title), 'parameter_name': filtro.parameter_name,
                          'lookups': _simples(filtro.lookups(None, None, modelo_admin))}
        for filtro in modelo_admin.list_filter if isinstance(filtro, type) and hasattr(filtro, 'parameter_name')
    }
    return {'classe': type(modelo_admin).__name__, **atributos, 'filtros_proprios': filtros_proprios,
            'funcoes': _funcoes_citadas(modelo_admin, planos)}


def _menu():
    usuario = SimpleNamespace(has_perm=lambda permissao: permissao)
    return [
        {
            'title': grupo.get('title'),
            'items': [
                {'title': item['title'], 'icon': item['icon'], 'link': str(item['link']),
                 'permission': item['permission'](SimpleNamespace(user=usuario)) if 'permission' in item else None}
                for item in grupo['items']
            ],
        }
        for grupo in tema.menu_lateral(None)
    ]


def retrato_atual():
    return {
        'site': {'index_template': admin.site.index_template, 'index_title': admin.site.index_title},
        'admins': {
            modelo._meta.label: _retrato_do_admin(modelo_admin)
            for modelo, modelo_admin in sorted(admin.site._registry.items(), key=lambda par: par[0]._meta.label)
        },
        'menu': _menu(),
        'favicons': tema.favicons(None),
    }


class RetratoDoAdminTest(SimpleTestCase):

    def test_configuracao_confere_com_o_retrato(self):
        atual = json.loads(json.dumps(retrato_atual(), ensure_ascii=False))
        if os.environ.get('RETRATO_ATUALIZAR') == '1':
            RETRATO.parent.mkdir(exist_ok=True)
            RETRATO.write_text(json.dumps(atual, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        self.maxDiff = None
        self.assertEqual(atual, json.loads(RETRATO.read_text(encoding='utf-8')))
