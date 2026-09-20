import os
import importlib
import config.settings

def test_csrf_trusted_origins_for_custom_host(monkeypatch):
    monkeypatch.setenv('DJANGO_ALLOWED_HOSTS', 'meu-app.onrender.com')
    importlib.reload(config.settings)
    assert 'https://meu-app.onrender.com' in config.settings.CSRF_TRUSTED_ORIGINS