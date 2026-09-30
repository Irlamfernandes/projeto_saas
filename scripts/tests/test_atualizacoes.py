import io
import json
import runpy
import sys
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import pytest
from scripts import atualizacoes as at
from scripts.atualizacoes import Atualizacao

AGORA = datetime(2026, 9, 29, 12, 0, tzinfo=UTC)


def _pypi(versoes, urls_do_projeto=None, datas=('2026-09-20T10:00:00Z',)):
    """Função falsa no lugar do acesso ao PyPI: {nome: versão mais nova}."""
    def baixar(url):
        nome = url.split('/pypi/')[1].split('/')[0]
        return {
            'info': {'version': versoes[nome], 'project_urls': urls_do_projeto},
            'urls': [{'upload_time_iso_8601': data} for data in datas],
        }
    return baixar


def _saida(codigo=0, stdout=''):
    return SimpleNamespace(returncode=codigo, stdout=stdout)


def _projeto(tmp_path, producao="Django==6.1.1\nrequests==2.34.2  # http\n", dev="-r requirements.txt\npytest==9.1.1\n"):
    (tmp_path / 'requirements.txt').write_text(producao)
    (tmp_path / 'requirements-dev.txt').write_text(dev)
    return tmp_path


class TestTipoDeMudanca:

    @pytest.mark.parametrize('atual, nova, tipo', [
        ('5.2.1', '6.0.0', 'principal'),
        ('0.16.9', '0.17.0', 'principal'),   # em 0.x o segundo número é o que quebra
        ('0.16.9', '0.16.10', 'correção'),
        ('6.1.1', '6.2.0', 'novidades'),
        ('6.1.1', '6.1.2', 'correção'),
        ('2026.7.22', '2026.9.1', 'novidades'),
        ('latest', '6.1.2', 'outra'),
    ])
    def test_classifica_pelo_numero_da_versao(self, atual, nova, tipo):
        assert at.tipo_de_mudanca(atual, nova) == tipo

    def test_atualizacao_sabe_o_proprio_tipo(self):
        assert Atualizacao('Python', 'x', '1.0', '2.0').tipo == 'principal'


class TestRequirements:

    def test_le_so_as_linhas_fixadas(self):
        texto = "# comentário\n-r requirements.txt\n\nDjango==6.1.1\nruff==0.16.9  # linter\nsem-versao\n"
        assert at.fixadas(texto) == {'Django': '6.1.1', 'ruff': '0.16.9'}

    def test_troca_a_versao_sem_mexer_no_resto_da_linha(self):
        texto = "Django==6.1.1\nruff==0.16.9  # linter\n-r requirements.txt"
        assert at.trocar_versoes(texto, {'django': '6.2.0', 'RUFF': '0.17.0'}) == (
            "Django==6.2.0\nruff==0.17.0  # linter\n-r requirements.txt"
        )


class TestOndeLerOQueMudou:

    def test_prefere_changelog_depois_repositorio_depois_o_padrao(self):
        assert at.link_do_que_mudou({'Homepage': 'h', 'Release notes': 'r'}, 'p') == 'r'
        assert at.link_do_que_mudou({'Documentation': 'd', 'Source': 's'}, 'p') == 's'
        assert at.link_do_que_mudou({'Documentation': 'd'}, 'p') == 'p'

    def test_repositorio_do_npm_vira_pagina_de_releases_so_no_github(self):
        assert at._repositorio_npm({'url': 'git+https://github.com/jestjs/jest.git'}) == 'https://github.com/jestjs/jest/releases'
        assert at._repositorio_npm('ssh://git@github.com/a/b.git') == 'https://github.com/a/b/releases'
        assert at._repositorio_npm('git://github.com/a/b') == 'https://github.com/a/b/releases'
        assert at._repositorio_npm({'url': 'https://gitlab.com/a/b'}) == ''
        assert at._repositorio_npm(None) == ''

    def test_consulta_o_pypi(self):
        baixar = _pypi({'django': '6.2.0'}, {'Changelog': 'https://c'}, ('2026-09-21T00:00:00Z', '2026-09-20T00:00:00Z'))
        versao, publicada, link = at.consultar_pypi('django', baixar)
        assert (versao, publicada, link) == ('6.2.0', datetime(2026, 9, 20, tzinfo=UTC), 'https://c')

    def test_pypi_sem_arquivos_e_sem_links(self):
        baixar = lambda url: {'info': {'version': '1.0'}, 'urls': None}  # noqa: E731
        assert at.consultar_pypi('x', baixar) == ('1.0', None, 'https://pypi.org/project/x/#history')

    def test_baixa_o_json_do_endereco(self):
        with patch('urllib.request.urlopen', return_value=io.BytesIO(b'{"ok": 1}')) as abrir:
            assert at._baixar_json('https://pypi.org/pypi/x/json') == {'ok': 1}
        abrir.assert_called_once_with('https://pypi.org/pypi/x/json', timeout=30)

    def test_baixar_so_por_https(self):
        with patch('urllib.request.urlopen') as abrir, pytest.raises(ValueError, match="sem HTTPS: file:///etc/passwd"):
            at._baixar_json('file:///etc/passwd')
        abrir.assert_not_called()


class TestPendentes:

    def test_python_lista_so_o_que_tem_versao_nova_em_ordem(self, tmp_path):
        raiz = _projeto(tmp_path)
        pendentes = at.pendentes_python(raiz, _pypi({'Django': '6.2.0', 'requests': '2.34.2', 'pytest': '9.2.0'}))
        assert [(a.nome, a.atual, a.nova) for a in pendentes] == [('Django', '6.1.1', '6.2.0'), ('pytest', '9.1.1', '9.2.0')]
        assert pendentes[0].ecossistema == 'Python'

    def test_js_usa_o_npm_outdated_e_o_npm_view(self):
        chamadas = []

        def rodar(comando):
            chamadas.append(comando)
            if comando[1] == 'outdated':
                return _saida(1, json.dumps({
                    'jest': {'current': '30.5.2', 'latest': '31.0.0'},
                    'globals': {'latest': '18.0.0'},
                }))
            if comando[2] == 'jest':
                return _saida(0, json.dumps({'time': {'31.0.0': '2026-09-01T00:00:00.000Z'},
                                             'repository': {'url': 'git+https://github.com/jestjs/jest.git'}}))
            return _saida(0, '')

        jest, globals_ = sorted(at.pendentes_js(rodar), key=lambda a: a.nome, reverse=True)
        assert (jest.atual, jest.nova, jest.link) == ('30.5.2', '31.0.0', 'https://github.com/jestjs/jest/releases')
        assert jest.publicada_em == datetime(2026, 9, 1, tzinfo=UTC)
        assert (globals_.atual, globals_.publicada_em) == ('?', None)
        assert globals_.link == 'https://www.npmjs.com/package/globals?activeTab=versions'
        assert chamadas[0] == ['npm', 'outdated', '--json']

    def test_js_em_dia(self):
        assert at.pendentes_js(lambda comando: _saida(0, '')) == []

    def test_rodar_chama_o_programa_na_raiz_do_projeto(self):
        with patch('subprocess.run', return_value='ok') as run:
            assert at._rodar(['npm', 'ci']) == 'ok'
        run.assert_called_once_with(['npm', 'ci'], cwd=at.RAIZ, capture_output=True, text=True, check=False)


class TestTestes:

    def test_python_instala_as_versoes_novas_num_ambiente_limpo(self, tmp_path):
        raiz = _projeto(tmp_path)
        vistos = []

        def rodar(comando):
            vistos.append(comando[1:3])
            if 'install' in comando:
                vistos.append(Path(comando[-1]).read_text())
            return _saida(0)

        assert at.testar_python([Atualizacao('Python', 'Django', '6.1.1', '6.2.0')], raiz, rodar)
        assert vistos[0] == ['-m', 'venv']
        assert vistos[2] == "Django==6.2.0\nrequests==2.34.2  # http\n\npytest==9.1.1\n"  # sem o '-r requirements.txt'
        assert vistos[3] == ['-m', 'pytest']

    def test_python_para_no_primeiro_passo_que_falha(self, tmp_path):
        passos = []

        def rodar(comando):
            passos.append(comando)
            return _saida(1 if 'install' in comando else 0)

        assert not at.testar_python([], _projeto(tmp_path), rodar)
        assert len(passos) == 2

    def test_js_troca_so_as_versoes_novas_e_roda_lint_testes_e_css(self):
        passos = []
        assert at.testar_js([Atualizacao('JavaScript', 'jest', '30', '31')], lambda c: passos.append(c) or _saida(0))
        assert passos[1][-1] == 'jest@31'
        assert [p[:3] for p in passos[2:]] == [['npm', 'run', '-s'], ['npx', 'jest', '--silent'], ['npm', 'run', '-s']]

    def test_js_que_falha(self):
        assert not at.testar_js([], lambda comando: _saida(1))


class TestVerificar:

    def _lista(self):
        return [Atualizacao('Python', nome, '1.0', '1.1') for nome in ('a', 'b')]

    def test_sem_nada_nao_testa(self):
        at.verificar([], lambda lista: pytest.fail('não devia testar'))

    def test_todas_juntas_passam(self):
        lista = self._lista()
        at.verificar(lista, lambda testadas: True)
        assert [a.testes for a in lista] == ['passam', 'passam']

    def test_acha_a_culpada_uma_por_uma(self):
        lista = self._lista()
        at.verificar(lista, lambda testadas: len(testadas) == 1 and testadas[0].nome == 'a')
        assert [a.testes for a in lista] == ['passam', 'falham']

    def test_cada_uma_passa_mas_juntas_quebram(self):
        lista = self._lista()
        at.verificar(lista, lambda testadas: len(testadas) == 1)
        assert [a.testes for a in lista] == ['só juntas', 'só juntas']


class TestRelatorio:

    def test_tudo_em_dia(self):
        assert at.relatorio([], AGORA) == "## Tudo em dia ✅\n\nNenhuma biblioteca com versão nova em 29/09/2026.\n"

    def test_separa_o_que_e_so_atualizar_do_que_precisa_mexer(self):
        lista = [
            Atualizacao('Python', 'django', '6.1.1', '6.1.2', datetime(2026, 9, 28, 12, tzinfo=UTC), 'https://c', 'passam'),
            Atualizacao('JavaScript', 'jest', '30.0.0', '31.0.0', datetime(2026, 9, 19, tzinfo=UTC), 'https://j', 'falham'),
            Atualizacao('Python', 'ruff', '0.16.9', '0.17.0', None, 'https://r'),
        ]
        texto = at.relatorio(lista, AGORA)
        assert "## 3 biblioteca(s) com versão nova — 29/09/2026" in texto
        assert "**Só atualizar** (testes passam): `django`" in texto
        assert "**Precisa mexer no código** (testes falham): `jest`" in texto
        assert "| Python · `django` | 6.1.2 |" not in texto
        assert "| Python · `django` | 6.1.1 | **6.1.2** | Correção | 28/09/2026 (1 dia) | ✅ passam | [ler](https://c) |" in texto
        assert "| JavaScript · `jest` | 30.0.0 | **31.0.0** | Principal ⚠️ | 19/09/2026 (10 dias) | ❌ falham |" in texto
        assert "| Python · `ruff` | 0.16.9 | **0.17.0** | Principal ⚠️ | — | — não testado |" in texto

    def test_nenhuma_em_cada_grupo(self):
        texto = at.relatorio([Atualizacao('Python', 'x', '1', '2')], AGORA)
        assert "(testes passam): nenhuma" in texto
        assert "(testes falham): nenhuma" in texto


class TestAplicar:

    def test_troca_so_nos_arquivos_onde_a_biblioteca_esta(self, tmp_path):
        raiz = _projeto(tmp_path)
        dev_antes = (raiz / 'requirements-dev.txt').stat().st_mtime_ns
        trocas = at.aplicar(['django'], raiz, _pypi({'Django': '6.2.0'}))
        assert trocas == {'Django': ('6.1.1', '6.2.0')}
        assert (raiz / 'requirements.txt').read_text() == "Django==6.2.0\nrequests==2.34.2  # http\n"
        assert (raiz / 'requirements-dev.txt').stat().st_mtime_ns == dev_antes


class TestLinhaDeComando:

    def test_aplicar(self, tmp_path):
        saida = io.StringIO()
        codigo = at.main(['aplicar', 'Django'], saida, raiz=_projeto(tmp_path), baixar=_pypi({'Django': '6.2.0'}))
        assert (codigo, saida.getvalue()) == (0, 'Django: 6.1.1 → 6.2.0\n')

    def test_aplicar_o_que_nao_esta_fixado(self, tmp_path):
        saida = io.StringIO()
        codigo = at.main(['aplicar', 'nada'], saida, raiz=_projeto(tmp_path), baixar=_pypi({}))
        assert (codigo, saida.getvalue()) == (1, 'Não estão fixadas nos requirements: nada\n')

    def test_relatorio_sem_testar(self, tmp_path):
        saida = io.StringIO()
        codigo = at.main(['relatorio'], saida, AGORA, raiz=_projeto(tmp_path),
                         baixar=_pypi({'Django': '6.1.1', 'requests': '2.34.2', 'pytest': '9.1.1'}),
                         rodar=lambda comando: _saida(0, ''))
        assert (codigo, saida.getvalue()) == (0, at.relatorio([], AGORA))

    def test_relatorio_testando(self, tmp_path):
        def rodar(comando):
            if comando[:2] == ['npm', 'outdated']:
                return _saida(1, json.dumps({'jest': {'current': '30.0.0', 'latest': '30.1.0'}}))
            return _saida(0, '{}')

        saida = io.StringIO()
        at.main(['relatorio', '--testar'], saida, AGORA, raiz=_projeto(tmp_path),
                baixar=_pypi({'Django': '6.1.2', 'requests': '2.34.2', 'pytest': '9.1.1'}), rodar=rodar)
        assert "**Só atualizar** (testes passam): `Django`, `jest`" in saida.getvalue()

    def test_usa_a_hora_atual_quando_nao_informada(self, tmp_path):
        saida = io.StringIO()
        at.main(['relatorio'], saida, raiz=_projeto(tmp_path), baixar=_pypi({'Django': '6.1.1', 'requests': '2.34.2', 'pytest': '9.1.1'}),
                rodar=lambda comando: _saida(0, ''))
        assert "Nenhuma biblioteca com versão nova" in saida.getvalue()

    def test_roda_como_script(self, monkeypatch):
        monkeypatch.setattr(sys, 'argv', ['atualizacoes.py', 'aplicar', 'biblioteca-que-nao-existe'])
        with pytest.raises(SystemExit) as saiu:
            runpy.run_path(at.__file__, run_name='__main__')
        assert saiu.value.code == 1
