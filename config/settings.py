import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key
from django.templatetags.static import static

BASE_DIR = Path(__file__).resolve().parent.parent

def _env_bool(nome, padrao):
    return os.environ.get(nome, str(padrao)) == 'True'


DEBUG = _env_bool('DJANGO_DEBUG', False)

# Em produção (DEBUG desligado) a chave é obrigatória: nunca cair numa chave conhecida.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY no ambiente (obrigatória com DJANGO_DEBUG desligado).")
    # Desenvolvimento sem chave: uma aleatória a cada início (as sessões locais caem ao reiniciar).
    SECRET_KEY = get_random_secret_key()

# Trata hosts permitidos
raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in raw_hosts.split(',') if host.strip()]

# Gera CSRF_TRUSTED_ORIGINS dinamicamente com segurança
CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    if host in ['localhost', '127.0.0.1', '*']:
        CSRF_TRUSTED_ORIGINS.append(f'http://{host}') # NOSONAR
        CSRF_TRUSTED_ORIGINS.append(f'https://{host}')
    else:
        CSRF_TRUSTED_ORIGINS.append(f'https://{host}')

# Application definition
INSTALLED_APPS = [
    'unfold',  # tema do admin: precisa vir antes do django.contrib.admin
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'infrastructure.apps.InfrastructureConfig',
    'interfaces',
    'config',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'interfaces.seguranca.PoliticaDeSegurancaMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'interfaces.seguranca.SemCacheParaQuemEstaLogadoMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Arquivos estáticos com a versão no nome (output.3f2a1b.css) e comprimidos: o navegador guarda por 1 ano
# e só baixa de novo quando o arquivo muda. (STATICFILES_STORAGE saiu no Django 5.1 e era ignorado.)
STORAGES = {
    'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage'},
}
ROOT_URLCONF = 'config.urls'
LOGIN_URL = 'login'
# Só o login do admin usa este destino (quando não há ?next=). O login do sistema tem o próprio redirecionamento.
LOGIN_REDIRECT_URL = 'admin:index'
LOGOUT_REDIRECT_URL = '/login/'

# Templates (Mantendo o caminho correto das suas interfaces)
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'interfaces' / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'interfaces.context_processors.plano',
                'interfaces.context_processors.desenvolvedor',
                'interfaces.context_processors.tema',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

# Model de Usuário
AUTH_USER_MODEL = 'infrastructure.UsuarioModel'
AUTHENTICATION_BACKENDS = ['infrastructure.autenticacao.BackendComLoja']

# Configuração de Banco com fallback local e suporte a SSL no Supabase
DEFAULT_DB_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASE_URL = os.environ.get('DATABASE_URL')
IS_PRODUCTION = bool(DATABASE_URL)

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL or DEFAULT_DB_URL,
        conn_max_age=600,
        conn_health_checks=True,  # conexões persistentes podem ser fechadas pelo Supabase
        ssl_require=os.environ.get('DATABASE_SSL_REQUIRE', str(IS_PRODUCTION)) == 'True',
    )
}

if DATABASES['default']['ENGINE'] == 'django.db.backends.postgresql':
    # Os poolers do Supabase compartilham conexões entre clientes: um search_path alterado por
    # outro cliente (ex.: "vault") pode vazar para a nossa sessão e o Django passa a procurar/criar
    # tabelas no schema errado. Fixar o search_path em toda conexão elimina isso.
    DATABASES['default'].setdefault('OPTIONS', {})['options'] = '-c search_path=public'
    # Exigido pelo Django com pooler em modo transação (porta 6543), onde cursores de servidor quebram.
    DATABASES['default']['DISABLE_SERVER_SIDE_CURSORS'] = True

# Segurança em produção (atrás do proxy HTTPS do Render)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = _env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Comece baixo e aumente (ex.: 31536000) depois de confirmar que tudo funciona só em HTTPS.
    # 1 ano: o navegador passa a só abrir o site por HTTPS (o recomendado é no mínimo 6 meses).
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '31536000'))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    # Preload exige domínio próprio (ex.: meusistema.com.br); um endereço *.onrender.com não entra na lista.
    SILENCED_SYSTEM_CHECKS = ['security.W021']

# Validação de senhas
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Internacionalização
LANGUAGE_CODE = 'pt-br'
TIME_ZONE = 'America/Sao_Paulo'
USE_I18N = True
# Traduções próprias (o tema do admin não vem em português): locale/pt_BR. Compile com `make traducoes`.
LOCALE_PATHS = [BASE_DIR / 'locale']
USE_TZ = True

# Arquivos Estáticos
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Armazenamento de imagens (Supabase Storage)
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')

# Pagamento do plano (Pix pelo Mercado Pago). Token TEST-... gera Pix de teste, que não pode ser pago.
MERCADO_PAGO_ACCESS_TOKEN = os.environ.get('MERCADO_PAGO_ACCESS_TOKEN', '')

# Tema do admin (django-unfold): cores Petróleo, menu organizado e painel com gráficos.
# Menu, favicon e painel ficam em infrastructure/admin/tema.py e painel.py.
UNFOLD = {
    'SITE_TITLE': 'GestCor',
    'SITE_HEADER': 'GestCor',
    'SITE_SUBHEADER': 'Administração · CorsariosCode',
    'SITE_URL': '/dashboard/',
    'SITE_ICON': lambda request: static('images/logo.svg'),
    'SITE_FAVICONS': 'infrastructure.admin.tema.favicons',
    # Olhinho nos campos de senha, o mesmo do site (login do admin incluído).
    'STYLES': [lambda request: static('css/mostrar_senha.css')],
    'SCRIPTS': [lambda request: static('js/mostrar_senha.js')],
    'SHOW_VIEW_ON_SITE': False,
    'SHOW_HISTORY': True,
    'DASHBOARD_CALLBACK': 'infrastructure.admin.painel.painel_do_admin',
    'COLORS': {
        'primary': {
            '50': '#f0f9f8', '100': '#e6f4f2', '200': '#c4e6e1', '300': '#8fd0c7', '400': '#2fb3a5',
            '500': '#0d9488', '600': '#0f766e', '700': '#115e59', '800': '#134e4a', '900': '#0f3d3a',
            '950': '#042f2e',
        },
    },
    'SIDEBAR': {
        'show_search': True,
        'show_all_applications': False,
        'navigation': 'infrastructure.admin.tema.menu_lateral',
    },
}

# Log: tudo para o console (é o que aparece no log do Render) e os erros também para a tela "Erros do sistema"
# do admin (infrastructure/registro_de_erros.py). Sem isto, com DEBUG desligado, o Django não escreve em lugar
# nenhum o erro das páginas que quebram (erro 500).
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {'padrao': {
        '()': 'infrastructure.registro_de_erros.SemDadosPessoais', 'format': '{levelname} {name}: {message}', 'style': '{',
    }},
    'filters': {'sem_avisos_de_seguranca': {'()': 'infrastructure.registro_de_erros.SemAvisosDeSeguranca'}},
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'padrao'},
        'erros_do_sistema': {
            'class': 'infrastructure.registro_de_erros.GuardarErroNoBanco',
            'level': 'ERROR',
            'filters': ['sem_avisos_de_seguranca'],
        },
    },
    'root': {'handlers': ['console', 'erros_do_sistema'], 'level': 'INFO'},
    # Os do Django passam a seguir para a raiz (o padrão dele só escreve no console com DEBUG ligado).
    'loggers': {'django': {'handlers': [], 'level': 'INFO', 'propagate': True}},
}

# Backup (infrastructure/admin/backup_admin.py e application/backup/services.py).
# BACKUP_CHAVE criptografa os arquivos: guarde-a também fora do Render — sem ela, nenhum backup abre.
# BACKUP_TOKEN autoriza o agendador a chamar /interno/backup/ (vazio = endereço desligado).
BACKUP_CHAVE = os.environ.get('BACKUP_CHAVE', '')
BACKUP_TOKEN = os.environ.get('BACKUP_TOKEN', '')
