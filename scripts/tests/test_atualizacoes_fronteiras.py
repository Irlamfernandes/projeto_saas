"""Detalhes exatos do verificador de atualizações (achados pelo teste de mutação)."""
import io
import json
from datetime import UTC, datetime
from pathlib import Path
import pytest
from scripts import atualizacoes as at
from scripts.atualizacoes import Atualizacao
from scripts.tests.test_atualizacoes import AGORA, _projeto, _pypi, _saida


class TestDetalhes:

    def test_valores_padrao(self):
        a = Atualizacao('Python', 'x', '1', '2')
        assert (a.publicada_em, a.link, a.testes) == (None, '', '')

    def test_numeros_da_versao(self):
        assert at._numeros('1.2.3.4') == (1, 2, 3)
        assert at._numeros('2+local.9') == (2,)

    @pytest.mark.parametrize('rotulo', ['Changes', 'History', 'News', "What's new"])
    def test_palavras_de_changelog(self, rotulo):
        assert at.link_do_que_mudou({'Homepage': 'https://h', rotulo: 'https://c'}, 'padrão') == 'https://c'

    @pytest.mark.parametrize('rotulo', ['Repository', 'Code', 'GitHub', 'Homepage'])
    def test_palavras_de_repositorio(self, rotulo):
        assert at.link_do_que_mudou({'Docs': 'https://d', rotulo: 'https://r'}, 'padrão') == 'https://r'

    def test_repositorio_do_npm(self):
        assert at._repositorio_npm({}) == ''
        assert at._repositorio_npm(None) == ''
        assert at._repositorio_npm('https://github.com/a/b') == 'https://github.com/a/b/releases'

    def test_endereco_do_pypi(self):
        pedidos = []

        def baixar(url):
            pedidos.append(url)
            return {'info': {'version': '1.0'}}
        at.consultar_pypi('Django', baixar)
        assert pedidos == ['https://pypi.org/pypi/Django/json']

    def test_python_em_ordem_de_nome(self, tmp_path):
        raiz = _projeto(tmp_path, producao="b==1.0\na==2.0\n", dev="")
        assert [a.nome for a in at.pendentes_python(raiz, _pypi({'a': '3.0', 'b': '3.0'}))] == ['a', 'b']

    def test_js_consulta_o_npm_view_com_data_e_repositorio(self):
        chamadas = []

        def rodar(comando):
            chamadas.append(comando)
            if comando[1] == 'outdated':
                return _saida(1, json.dumps({'jest': {'current': '30', 'latest': '31'}}))
            return _saida(0, json.dumps({'time': {'31': '2026-09-01T00:00:00.000Z'}}))
        [jest] = at.pendentes_js(rodar)
        assert chamadas[1] == ['npm', 'view', 'jest', 'time', 'repository', '--json']
        assert (jest.ecossistema, jest.publicada_em) == ('JavaScript', datetime(2026, 9, 1, tzinfo=UTC))


class TestComandos:

    def test_python(self, tmp_path):
        passos = []
        at.testar_python([], _projeto(tmp_path), lambda comando: passos.append(comando) or _saida(0))
        pasta = Path(passos[0][-1]).parent
        python = str(pasta / 'venv' / 'bin' / 'python')
        assert passos == [
            [at.sys.executable, '-m', 'venv', str(pasta / 'venv')],
            [python, '-m', 'pip', 'install', '-q', '-r', str(pasta / 'requirements.txt')],
            [python, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-x'],
        ]

    def test_js(self):
        passos = []
        novas = [Atualizacao('JavaScript', 'jest', '30', '31'), Atualizacao('JavaScript', 'globals', '17', '18')]
        at.testar_js(novas, lambda comando: passos.append(comando) or _saida(0))
        assert passos == [
            ['npm', 'ci', '--silent'],
            ['npm', 'install', '--no-save', '--silent', 'jest@31', 'globals@18'],
            ['npm', 'run', '-s', 'lint'],
            ['npx', 'jest', '--silent'],
            ['npm', 'run', '-s', 'build:css'],
        ]


class TestRelatorioCompleto:

    def test_texto_inteiro(self):
        lista = [
            Atualizacao('Python', 'a', '1.0.0', '1.1.0', None, 'https://a', 'passam'),
            Atualizacao('Python', 'b', '1.0.0', '1.0.1', None, 'https://b', 'passam'),
            Atualizacao('Python', 'c', 'x', 'y', None, 'https://c', 'só juntas'),
            Atualizacao('Python', 'd', '1', '2', None, 'https://d', 'falham'),
        ]
        assert at.relatorio(lista, AGORA) == '\n'.join([
            "## 4 biblioteca(s) com versão nova — 29/09/2026",
            "",
            "- **Só atualizar** (testes passam): `a`, `b`",
            "- **Precisa mexer no código** (testes falham): `c`, `d`",
            "",
            "| Biblioteca | Atual | Nova | Tipo | Publicada | Testes | O que mudou |",
            "|---|---|---|---|---|---|---|",
            "| Python · `a` | 1.0.0 | **1.1.0** | Novidades | — | ✅ passam | [ler](https://a) |",
            "| Python · `b` | 1.0.0 | **1.0.1** | Correção | — | ✅ passam | [ler](https://b) |",
            "| Python · `c` | x | **y** | Outra | — | ⚠️ só falham juntas | [ler](https://c) |",
            "| Python · `d` | 1 | **2** | Principal ⚠️ | — | ❌ falham | [ler](https://d) |",
            "",
            "**Tipo:** *Principal* pode exigir mudança no código (leia o que mudou); *Novidades* e *Correção* normalmente não.",
            "**Publicada há menos de 7 dias:** vale esperar — versões com problema costumam ser retiradas nos primeiros dias.",
            "",
            "Para aplicar na `homologacao`: `make atualizar PACOTES=\"nome outro\"` (Python) ou `npm install -D nome@versão` (JS).",
        ]) + '\n'


class TestLinhaDeComandoDetalhes:

    def test_ajuda(self):
        parser = at.criar_parser()
        assert parser.description == (
            "Verificação de atualizações: o que tem versão nova, se os testes passam com ela e onde ler o que mudou."
        )
        [comandos] = parser._subparsers._group_actions
        assert {acao.dest: acao.help for acao in comandos._choices_actions} == {
            'relatorio': 'lista as versões novas (e testa com --testar)',
            'aplicar': 'troca a versão fixada nos requirements',
        }
        opcoes = {acao.dest: acao.help for acao in comandos.choices['relatorio']._actions}
        assert opcoes['testar'] == 'roda os testes com as versões novas'

    def test_comando_e_obrigatorio(self, capsys):
        with pytest.raises(SystemExit) as saiu:
            at.main([])
        assert saiu.value.code == 2
        assert "comando" in capsys.readouterr().err

    def test_varios_nao_fixados(self, tmp_path):
        saida = io.StringIO()
        at.main(['aplicar', 'b', 'a'], saida, raiz=_projeto(tmp_path), baixar=_pypi({}))
        assert saida.getvalue() == 'Não estão fixadas nos requirements: a, b\n'
