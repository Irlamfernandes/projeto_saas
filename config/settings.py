import os
from pathlib import Path
import dj_database_url
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

def _env_bool(nome, padrao):
    return os.environ.get(nome, str(padrao)) == 'True'


DEBUG = _env_bool('DJANGO_DEBUG', False)

# Em produção (DEBUG desligado) a chave é obrigatória: nunca cair numa chave conhecida.
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY') or os.getenv('SECRET_KEY')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured("Defina DJANGO_SECRET_KEY no ambiente (obrigatória com DJANGO_DEBUG desligado).")
    SECRET_KEY = 'django-insecure-somente-para-desenvolvimento-local'

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
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'
ROOT_URLCONF = 'config.urls'
LOGIN_URL = 'login'
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

# Segurança em produção (atrás do proxy HTTPS do Render)
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = _env_bool('DJANGO_SECURE_SSL_REDIRECT', True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # Comece baixo e aumente (ex.: 31536000) depois de confirmar que tudo funciona só em HTTPS.
    SECURE_HSTS_SECONDS = int(os.environ.get('DJANGO_HSTS_SECONDS', '3600'))

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
USE_TZ = True

# Arquivos Estáticos
STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Armazenamento de imagens (Supabase Storage)
SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
