"""Content Security Policy: diz ao navegador de onde a página pode carregar scripts, estilos, imagens e fontes.

Se alguém conseguir injetar um <script> ou um onclick no HTML, o navegador se recusa a rodar: nas telas do sistema
só roda JavaScript vindo dos arquivos em /static/. Por isso os templates não têm código inline (ações em data-*).
O admin (Unfold) depende de scripts inline e do Alpine.js, então tem uma política própria, mais flexível.
"""
from urllib.parse import urlsplit
from django.conf import settings
from django.utils.cache import add_never_cache_headers

CABECALHO = 'Content-Security-Policy'
PERMISSOES = 'Permissions-Policy'
# Recursos do aparelho que o sistema nunca usa: nem um script injetado consegue pedi-los.
# (Tirar foto do produto usa o seletor de arquivos do celular, que não depende da permissão de câmera.)
SEM_PERMISSOES = ', '.join(f"{recurso}=()" for recurso in (
    'camera', 'microphone', 'geolocation', 'payment', 'usb', 'serial', 'bluetooth', 'hid', 'midi',
    'magnetometer', 'gyroscope', 'accelerometer', 'display-capture', 'browsing-topics',
))
PREFIXO_DO_ADMIN = '/admin/'
PROPRIO = "'self'"
NENHUM = "'none'"
INLINE = "'unsafe-inline'"
DADOS = 'data:'


def origem_do_storage():
    """Fotos dos produtos e marcas das lojas ficam no Storage do Supabase (outro endereço)."""
    partes = urlsplit(settings.SUPABASE_URL or '')
    return f"{partes.scheme}://{partes.netloc}" if partes.scheme and partes.netloc else ''


def _montar(diretivas):
    return '; '.join(f"{nome} {' '.join(filter(None, fontes))}" for nome, fontes in diretivas.items())


def _comum():
    """Regras iguais para o site e o admin: tudo do próprio site, nada de plugins nem de ser aberto dentro de outro site."""
    return {
        'default-src': [PROPRIO],
        'style-src': [PROPRIO, INLINE],
        'img-src': [PROPRIO, DADOS, origem_do_storage()],
        'connect-src': [PROPRIO],
        'object-src': [NENHUM],
        'base-uri': [PROPRIO],
        'form-action': [PROPRIO],
        'frame-ancestors': [NENHUM],
    }


def politica_do_site():
    # style-src com inline: atributos style="" (mapa de horários, barra do celular) e estilos que o Chart.js aplica.
    # img-src com data: = QR code do Pix e ícones embutidos no CSS.
    return _montar({
        **_comum(),
        'script-src': [PROPRIO],
        'font-src': [PROPRIO],
        'manifest-src': [PROPRIO],
        'worker-src': [PROPRIO],
    })


def politica_do_admin():
    return _montar({
        **_comum(),
        'script-src': [PROPRIO, INLINE, "'unsafe-eval'"],
        'font-src': [PROPRIO, DADOS],
    })


class PoliticaDeSegurancaMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
        self.site = politica_do_site()
        self.admin = politica_do_admin()

    def __call__(self, request):
        response = self.get_response(request)
        if CABECALHO not in response:
            response[CABECALHO] = self.admin if request.path.startswith(PREFIXO_DO_ADMIN) else self.site
        response.setdefault(PERMISSOES, SEM_PERMISSOES)
        return response


class SemCacheParaQuemEstaLogadoMiddleware:
    """Páginas de quem está logado não ficam guardadas no navegador: depois de sair da conta, o botão voltar
    pede a página de novo ao servidor, que manda para o login (em vez de mostrar o painel guardado)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            add_never_cache_headers(response)
        return response
