"""Configurações da suíte de testes (usado pelo pytest.ini)."""
import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'chave-exclusiva-da-suite-de-testes')

from config.settings import *  # noqa: E402,F401,F403

# PBKDF2 é propositalmente lento; nos testes basta um hasher barato.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
# O cliente de testes fala HTTP; o redirecionamento para HTTPS é testado à parte.
SECURE_SSL_REDIRECT = False
