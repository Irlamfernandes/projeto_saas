import importlib.util
from pathlib import Path
import config.settings

ARQUIVO = Path(config.settings.__file__).with_name('settings_homologacao.py')


def _carregar(monkeypatch, **ambiente):
    for nome, valor in ambiente.items():
        monkeypatch.setenv(nome, valor)
    spec = importlib.util.spec_from_file_location('homologacao_isolada', ARQUIVO)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_funciona_em_http_na_rede_local(monkeypatch):
    homologacao = _carregar(monkeypatch)
    assert homologacao.SECURE_SSL_REDIRECT is False
    assert homologacao.SESSION_COOKIE_SECURE is False
    assert homologacao.CSRF_COOKIE_SECURE is False
    assert homologacao.SECURE_HSTS_SECONDS == 0
    assert homologacao.CSRF_TRUSTED_ORIGINS == config.settings.CSRF_TRUSTED_ORIGINS  # nenhuma origem em HTTP


def test_resto_igual_a_producao(monkeypatch):
    homologacao = _carregar(monkeypatch)
    assert homologacao.MIDDLEWARE == config.settings.MIDDLEWARE
    assert homologacao.STORAGES['staticfiles'] == config.settings.STORAGES['staticfiles']

