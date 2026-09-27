import importlib.util
import pytest
from django.core.exceptions import ImproperlyConfigured
import config.settings


@pytest.fixture
def recarregar(monkeypatch):
    """Executa config/settings.py num módulo novo e isolado, com o ambiente informado."""
    def _recarregar(**ambiente):
        for nome in ('DJANGO_DEBUG', 'DJANGO_SECRET_KEY', 'SECRET_KEY', 'DJANGO_SECURE_SSL_REDIRECT', 'DJANGO_HSTS_SECONDS'):
            monkeypatch.delenv(nome, raising=False)
        for nome, valor in ambiente.items():
            monkeypatch.setenv(nome, valor)
        spec = importlib.util.spec_from_file_location('settings_isolado', config.settings.__file__)
        modulo = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(modulo)
        return modulo

    return _recarregar


def test_csrf_trusted_origins_for_custom_host(recarregar):
    settings = recarregar(DJANGO_SECRET_KEY='x', DJANGO_ALLOWED_HOSTS='meu-app.onrender.com')
    assert 'https://meu-app.onrender.com' in settings.CSRF_TRUSTED_ORIGINS


def test_producao_sem_secret_key_falha_ao_subir(recarregar):
    """Antes caía silenciosamente numa chave fixa e pública."""
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        recarregar()


def test_desenvolvimento_sem_secret_key_usa_chave_aleatoria(recarregar):
    """Nenhuma chave fica escrita no código: cada início gera outra."""
    primeira = recarregar(DJANGO_DEBUG='True').SECRET_KEY
    segunda = recarregar(DJANGO_DEBUG='True').SECRET_KEY
    assert len(primeira) >= 50
    assert primeira != segunda


def test_aceita_o_nome_alternativo_secret_key(recarregar):
    assert recarregar(SECRET_KEY='alternativa').SECRET_KEY == 'alternativa'


def test_producao_liga_https_cookies_seguros_e_hsts(recarregar):
    settings = recarregar(DJANGO_SECRET_KEY='x')
    assert settings.SECURE_SSL_REDIRECT is True
    assert settings.SESSION_COOKIE_SECURE is True
    assert settings.CSRF_COOKIE_SECURE is True
    assert settings.SECURE_HSTS_SECONDS == 31536000
    assert settings.SECURE_HSTS_INCLUDE_SUBDOMAINS is True
    assert settings.SECURE_PROXY_SSL_HEADER == ('HTTP_X_FORWARDED_PROTO', 'https')


def test_producao_permite_ajustar_redirect_e_hsts(recarregar):
    settings = recarregar(DJANGO_SECRET_KEY='x', DJANGO_SECURE_SSL_REDIRECT='False', DJANGO_HSTS_SECONDS='31536000')
    assert settings.SECURE_SSL_REDIRECT is False
    assert settings.SECURE_HSTS_SECONDS == 31536000


def test_desenvolvimento_nao_forca_https(recarregar):
    settings = recarregar(DJANGO_DEBUG='True')
    assert not hasattr(settings, 'SECURE_SSL_REDIRECT')
    assert not hasattr(settings, 'SESSION_COOKIE_SECURE')


def test_validadores_de_senha(recarregar):
    settings = recarregar(DJANGO_SECRET_KEY='x')
    nomes = [v['NAME'].rsplit('.', 1)[1] for v in settings.AUTH_PASSWORD_VALIDATORS]
    assert nomes == [
        'UserAttributeSimilarityValidator', 'MinimumLengthValidator',
        'CommonPasswordValidator', 'NumericPasswordValidator',
    ]
    assert settings.AUTH_PASSWORD_VALIDATORS[1]['OPTIONS'] == {'min_length': 8}


def test_login_url_aponta_para_a_tela_de_login(recarregar):
    assert recarregar(DJANGO_SECRET_KEY='x').LOGIN_URL == 'login'


def test_backend_de_autenticacao_e_conexao(recarregar):
    settings = recarregar(DJANGO_SECRET_KEY='x')
    assert settings.AUTHENTICATION_BACKENDS == ['infrastructure.autenticacao.BackendComLoja']
    assert settings.DATABASES['default']['CONN_HEALTH_CHECKS'] is True


def test_postgres_fixa_search_path_e_desliga_cursores_de_servidor(recarregar):
    """Regressão: pelo pooler do Supabase a conexão às vezes vinha com search_path=vault e o
    migrate tentava criar django_migrations no schema errado (permission denied for schema vault)."""
    banco = recarregar(DJANGO_SECRET_KEY='x', DATABASE_URL='postgresql://u:s@db.exemplo.com:5432/postgres').DATABASES['default']
    assert banco['OPTIONS']['options'] == '-c search_path=public'
    assert banco['DISABLE_SERVER_SIDE_CURSORS'] is True


def test_sqlite_local_nao_recebe_opcoes_de_postgres(recarregar):
    banco = recarregar(DJANGO_DEBUG='True').DATABASES['default']
    assert banco['ENGINE'] == 'django.db.backends.sqlite3'
    assert 'options' not in banco.get('OPTIONS', {})


def test_producao_serve_estaticos_com_versao_no_nome_e_comprimidos(recarregar):
    """Com o nome versionado, o navegador guarda CSS e JS por 1 ano e só baixa de novo quando mudam."""
    storages = recarregar(DJANGO_SECRET_KEY='x').STORAGES
    assert storages['staticfiles']['BACKEND'] == 'whitenoise.storage.CompressedManifestStaticFilesStorage'
    assert not hasattr(recarregar(DJANGO_SECRET_KEY='x'), 'STATICFILES_STORAGE')  # removido no Django 5.1
