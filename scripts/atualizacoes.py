"""Verificação de atualizações: o que tem versão nova, se os testes passam com ela e onde ler o que mudou.

Roda toda semana no GitHub Actions (.github/workflows/atualizacoes.yml) e publica o resultado numa issue.
Localmente: `make atualizacoes` (só a lista) e `make atualizar PACOTES="nome outro"` (troca a versão fixada).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
REQUISITOS = ('requirements.txt', 'requirements-dev.txt')
FIXADA = re.compile(r'^(?P<nome>[A-Za-z0-9][A-Za-z0-9._-]*)==(?P<versao>[^\s#;]+)')
PALAVRAS_DE_CHANGELOG = ('changelog', 'changes', 'release', 'history', 'news', 'what')
PALAVRAS_DE_REPOSITORIO = ('source', 'repository', 'code', 'github', 'homepage')
TIPOS = {'principal': 'Principal ⚠️', 'novidades': 'Novidades', 'correção': 'Correção', 'outra': 'Outra'}
SO_JUNTAS = 'só juntas'  # cada uma passa sozinha, mas os testes falham com todas juntas
RESULTADOS = {'passam': '✅ passam', 'falham': '❌ falham', SO_JUNTAS: '⚠️ só falham juntas', '': '— não testado'}


@dataclass
class Atualizacao:
    ecossistema: str  # 'Python' ou 'JavaScript'
    nome: str
    atual: str
    nova: str
    publicada_em: datetime | None = None
    link: str = ''
    testes: str = ''

    @property
    def tipo(self):
        return tipo_de_mudanca(self.atual, self.nova)


# ---------- versões ----------

def _numeros(versao):
    return tuple(int(parte) for parte in re.findall(r'\d+', versao.split('+')[0])[:3])


def tipo_de_mudanca(atual, nova):
    """Principal pode quebrar o código; novidades e correções normalmente não. Em 0.x, subir o segundo número já é principal."""
    antes, depois = _numeros(atual), _numeros(nova)
    if not antes or not depois:
        return 'outra'
    if depois[0] != antes[0] or (antes[0] == 0 and depois[1:2] != antes[1:2]):
        return 'principal'
    return 'novidades' if depois[1:2] != antes[1:2] else 'correção'


def fixadas(texto):
    """{nome: versão} das linhas 'nome==versão' de um requirements."""
    return {m['nome']: m['versao'] for linha in texto.splitlines() if (m := FIXADA.match(linha.strip()))}


def trocar_versoes(texto, novas):
    """O mesmo requirements com as versões de `novas` ({nome: versão}) no lugar das atuais; o resto da linha fica."""
    minusculas = {nome.lower(): versao for nome, versao in novas.items()}

    def trocar(linha):
        m = FIXADA.match(linha)
        if not m or m['nome'].lower() not in minusculas:
            return linha
        return f"{m['nome']}=={minusculas[m['nome'].lower()]}{linha[m.end():]}"
    return '\n'.join(trocar(linha) for linha in texto.split('\n'))


# ---------- onde ler o que mudou ----------

def link_do_que_mudou(urls, padrao):
    """Prefere a página de changelog/releases; senão o repositório; senão `padrao`."""
    for palavras in (PALAVRAS_DE_CHANGELOG, PALAVRAS_DE_REPOSITORIO):
        for rotulo, url in urls.items():
            if any(palavra in rotulo.lower() for palavra in palavras):
                return url
    return padrao


def _baixar_json(url):
    if not url.startswith('https://'):  # só HTTPS: file:// ou outro esquema leriam o disco ou falariam sem criptografia
        raise ValueError(f"Endereço sem HTTPS: {url}")
    with urllib.request.urlopen(url, timeout=30) as resposta:  # nosec B310: esquema conferido acima
        return json.load(resposta)


def consultar_pypi(nome, baixar=_baixar_json):
    """(versão mais nova, data de publicação, link do que mudou)."""
    dados = baixar(f'https://pypi.org/pypi/{nome}/json')
    arquivos = dados.get('urls') or []
    datas = [datetime.fromisoformat(arquivo['upload_time_iso_8601']) for arquivo in arquivos]
    link = link_do_que_mudou(dados['info'].get('project_urls') or {}, f'https://pypi.org/project/{nome}/#history')
    return dados['info']['version'], min(datas, default=None), link


def _repositorio_npm(repositorio):
    if isinstance(repositorio, dict):
        repositorio = repositorio.get('url')
    if not repositorio:
        return ''
    url = re.sub(r'(?:^git\+)|(?:\.git$)', '', repositorio).replace('git://', 'https://').replace('ssh://git@', 'https://')
    return f'{url}/releases' if 'github.com' in url else ''


# ---------- o que tem versão nova ----------

def _rodar(comando):
    return subprocess.run(comando, cwd=RAIZ, capture_output=True, text=True, check=False)


def pendentes_python(raiz=RAIZ, baixar=_baixar_json):
    versoes = {}
    for arquivo in REQUISITOS:
        versoes.update(fixadas((raiz / arquivo).read_text()))
    encontradas = []
    for nome, atual in sorted(versoes.items(), key=lambda par: par[0].lower()):
        nova, publicada, link = consultar_pypi(nome, baixar)
        if nova != atual:
            encontradas.append(Atualizacao('Python', nome, atual, nova, publicada, link))
    return encontradas


def pendentes_js(rodar=_rodar):
    # `npm outdated` sai com código 1 quando há algo desatualizado: o que importa é o JSON.
    desatualizados = json.loads(rodar(['npm', 'outdated', '--json']).stdout or '{}')
    encontradas = []
    for nome, info in sorted(desatualizados.items()):
        dados = json.loads(rodar(['npm', 'view', nome, 'time', 'repository', '--json']).stdout or '{}')
        publicada = dados.get('time', {}).get(info['latest'])
        link = _repositorio_npm(dados.get('repository')) or f'https://www.npmjs.com/package/{nome}?activeTab=versions'
        encontradas.append(Atualizacao(
            'JavaScript', nome, info.get('current') or '?', info['latest'],
            datetime.fromisoformat(publicada) if publicada else None, link,
        ))
    return encontradas


# ---------- os testes passam com a versão nova? ----------

def testar_python(atualizacoes, raiz=RAIZ, rodar=_rodar):
    """Instala tudo num ambiente novo com as versões novas e roda a suíte inteira."""
    novas = {a.nome: a.nova for a in atualizacoes}
    with tempfile.TemporaryDirectory() as pasta:
        pasta = Path(pasta)
        linhas = [trocar_versoes((raiz / arquivo).read_text(), novas) for arquivo in REQUISITOS]
        requisitos = pasta / 'requirements.txt'
        requisitos.write_text('\n'.join(linha for texto in linhas for linha in texto.split('\n') if not linha.startswith('-r ')))
        python = pasta / 'venv' / 'bin' / 'python'
        passos = (
            [sys.executable, '-m', 'venv', str(pasta / 'venv')],
            [str(python), '-m', 'pip', 'install', '-q', '-r', str(requisitos)],
            [str(python), '-m', 'pytest', '-q', '-p', 'no:cacheprovider', '-x'],
        )
        return all(rodar(passo).returncode == 0 for passo in passos)


def testar_js(atualizacoes, rodar=_rodar):
    """Parte do package-lock (npm ci), troca só as versões novas e roda lint, testes e o build do CSS."""
    passos = (
        ['npm', 'ci', '--silent'],
        ['npm', 'install', '--no-save', '--silent', *(f'{a.nome}@{a.nova}' for a in atualizacoes)],
        ['npm', 'run', '-s', 'lint'],
        ['npx', 'jest', '--silent'],
        ['npm', 'run', '-s', 'build:css'],
    )
    return all(rodar(passo).returncode == 0 for passo in passos)


def verificar(atualizacoes, testar):
    """Todas juntas primeiro; se quebrar, uma por uma para achar a culpada."""
    if not atualizacoes:
        return
    if testar(atualizacoes):
        for atualizacao in atualizacoes:
            atualizacao.testes = 'passam'
        return
    for atualizacao in atualizacoes:
        atualizacao.testes = 'passam' if testar([atualizacao]) else 'falham'
    if all(a.testes == 'passam' for a in atualizacoes):
        for atualizacao in atualizacoes:
            atualizacao.testes = SO_JUNTAS


# ---------- relatório ----------

def _data(momento, agora):
    if not momento:
        return '—'
    dias = (agora - momento).days
    return f"{momento:%d/%m/%Y} ({dias} dia{'s' if dias != 1 else ''})"


CABECALHO_DA_TABELA = ['| Biblioteca | Atual | Nova | Tipo | Publicada | Testes | O que mudou |', '|---|---|---|---|---|---|---|']
RODAPE = [
    '',
    '**Tipo:** *Principal* pode exigir mudança no código (leia o que mudou); *Novidades* e *Correção* normalmente não.',
    '**Publicada há menos de 7 dias:** vale esperar — versões com problema costumam ser retiradas nos primeiros dias.',
    '',
    'Para aplicar na `homologacao`: `make atualizar PACOTES="nome outro"` (Python) ou `npm install -D nome@versão` (JS).',
]


def _nomes(atualizacoes, resultados):
    """`a`, `b` das bibliotecas com um destes resultados de teste, ou "nenhuma"."""
    return ', '.join(f'`{a.nome}`' for a in atualizacoes if a.testes in resultados) or 'nenhuma'


def _linha_da_tabela(a, agora):
    return (f"| {a.ecossistema} · `{a.nome}` | {a.atual} | **{a.nova}** | {TIPOS[a.tipo]} | {_data(a.publicada_em, agora)} "
            f"| {RESULTADOS[a.testes]} | [ler]({a.link}) |")


def relatorio(atualizacoes, agora):
    if not atualizacoes:
        return f"## Tudo em dia ✅\n\nNenhuma biblioteca com versão nova em {agora:%d/%m/%Y}.\n"
    linhas = [
        f"## {len(atualizacoes)} biblioteca(s) com versão nova — {agora:%d/%m/%Y}",
        '',
        f"- **Só atualizar** (testes passam): {_nomes(atualizacoes, ('passam',))}",
        f"- **Precisa mexer no código** (testes falham): {_nomes(atualizacoes, ('falham', SO_JUNTAS))}",
        '',
        *CABECALHO_DA_TABELA,
        *(_linha_da_tabela(a, agora) for a in atualizacoes),
        *RODAPE,
    ]
    return '\n'.join(linhas) + '\n'


# ---------- aplicar ----------

def aplicar(nomes, raiz=RAIZ, baixar=_baixar_json):
    """Troca a versão fixada nos requirements pela mais nova. Devolve {nome: (antes, depois)}."""
    trocas = {}
    for arquivo in REQUISITOS:
        caminho = raiz / arquivo
        texto = caminho.read_text()
        atuais = {nome.lower(): (nome, versao) for nome, versao in fixadas(texto).items()}
        novas = {}
        for pedido in nomes:
            if pedido.lower() in atuais:
                nome, antes = atuais[pedido.lower()]
                novas[nome] = consultar_pypi(nome, baixar)[0]
                trocas[nome] = (antes, novas[nome])
        if novas:
            caminho.write_text(trocar_versoes(texto, novas))
    return trocas


def criar_parser():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    comandos = parser.add_subparsers(dest='comando', required=True)
    rel = comandos.add_parser('relatorio', help='lista as versões novas (e testa com --testar)')
    rel.add_argument('--testar', action='store_true', help='roda os testes com as versões novas')
    apl = comandos.add_parser('aplicar', help='troca a versão fixada nos requirements')
    apl.add_argument('pacotes', nargs='+')
    return parser


def main(argv=None, saida=sys.stdout, agora=None, **dependencias):
    args = criar_parser().parse_args(argv)

    baixar = dependencias.get('baixar', _baixar_json)
    rodar = dependencias.get('rodar', _rodar)
    raiz = dependencias.get('raiz', RAIZ)
    if args.comando == 'aplicar':
        trocas = aplicar(args.pacotes, raiz, baixar)
        for nome, (antes, depois) in trocas.items():
            saida.write(f'{nome}: {antes} → {depois}\n')
        faltando = sorted({p.lower() for p in args.pacotes} - {n.lower() for n in trocas})
        if faltando:
            saida.write(f"Não estão fixadas nos requirements: {', '.join(faltando)}\n")
        return 1 if faltando else 0

    python = pendentes_python(raiz, baixar)
    js = pendentes_js(rodar)
    if args.testar:
        verificar(python, lambda lista: testar_python(lista, raiz, rodar))
        verificar(js, lambda lista: testar_js(lista, rodar))
    saida.write(relatorio(python + js, agora or datetime.now(UTC)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
