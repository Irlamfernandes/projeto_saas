"""Content Security Policy: diz ao navegador de onde a página pode carregar scripts, estilos, imagens e fontes.

Se alguém conseguir injetar um <script> ou um onclick no HTML, o navegador se recusa a rodar: nas telas do sistema
só roda JavaScript vindo dos arquivos em /static/. Por isso os templates não têm código inline (ações em data-*).
O admin (Unfold) depende de scripts inline e do Alpine.js, então tem uma política própria, mais flexível.
"""
from urllib.parse import urlsplit
from django.conf import settings

CABECALHO = 'Content-Security-Policy'
PREFIXO_DO_ADMIN = '/admin/'


def origem_do_storage():
    """Fotos dos produtos e marcas das lojas ficam no Storage do Supabase (outro endereço)."""
    partes = urlsplit(settings.SUPABASE_URL or '')
    return f"{partes.scheme}://{partes.netloc}" if partes.scheme and partes.netloc else ''


def _montar(diretivas):
    return '; '.join(f"{nome} {' '.join(filter(None, fontes))}" for nome, fontes in diretivas.items())


def politica_do_site():
    return _montar({
        'default-src': ["'self'"],
        'script-src': ["'self'"],
        # Atributos style="" (mapa de horários, barra do celular) e estilos que o Chart.js aplica
        'style-src': ["'self'", "'unsafe-inline'"],
        # data: = QR code do Pix e ícones embutidos no CSS
        'img-src': ["'self'", 'data:', origem_do_storage()],
        'font-src': ["'self'"],
        'connect-src': ["'self'"],
        'manifest-src': ["'self'"],
        'worker-src': ["'self'"],
        'object-src': ["'none'"],
        'base-uri': ["'self'"],
        'form-action': ["'self'"],
        'frame-ancestors': ["'none'"],
    })


def politica_do_admin():
    return _montar({
        'default-src': ["'self'"],
        'script-src': ["'self'", "'unsafe-inline'", "'unsafe-eval'"],
        'style-src': ["'self'", "'unsafe-inline'"],
        'img-src': ["'self'", 'data:', origem_do_storage()],
        'font-src': ["'self'", 'data:'],
        'connect-src': ["'self'"],
        'object-src': ["'none'"],
        'base-uri': ["'self'"],
        'form-action': ["'self'"],
        'frame-ancestors': ["'none'"],
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
        return response
