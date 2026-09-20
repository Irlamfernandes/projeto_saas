import os
from pathlib import Path
import dj_database_url

BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = (
    os.getenv('DJANGO_SECRET_KEY')
    or os.getenv('SECRET_KEY')
    or 'django-insecure-dummy-key-for-tests-12345'
)

DEBUG = os.environ.get('DJANGO_DEBUG', 'False') == 'True'

# Trata hosts permitidos
raw_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1')
ALLOWED_HOSTS = [host.strip() for host in raw_hosts.split(',') if host.strip()]

# Gera CSRF_TRUSTED_ORIGINS dinamicamente para evitar erro 403 na Render
CSRF_TRUSTED_ORIGINS = []
for host in ALLOWED_HOSTS:
    if host not in ['localhost', '127.0.0.1', '*']:
        CSRF_TRUSTED_ORIGINS.append(f'https://{host}')
    CSRF_TRUSTED_ORIGINS.append(f'http://{host}')

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

# Configuração de Banco com fallback local e suporte a SSL no Supabase
DEFAULT_DB_URL = f"sqlite:///{BASE_DIR / 'db.sqlite3'}"
DATABASE_URL = os.environ.get('DATABASE_URL')
IS_PRODUCTION = bool(DATABASE_URL)

DATABASES = {
    'default': dj_database_url.config(
        default=DATABASE_URL or DEFAULT_DB_URL,
        conn_max_age=600,
        ssl_require=os.environ.get('DATABASE_SSL_REQUIRE', str(IS_PRODUCTION)) == 'True',
    )
}

# Configurações de segurança de cabeçalho em ambiente produtivo
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Validação de senhas
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 6,
        }
    },
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