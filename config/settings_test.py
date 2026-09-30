"""Configurações da suíte de testes (usado pelo pytest.ini)."""
import os

os.environ.setdefault('DJANGO_SECRET_KEY', 'chave-exclusiva-da-suite-de-testes')

from config.settings import *

# PBKDF2 é propositalmente lento; nos testes basta um hasher barato.
PASSWORD_HASHERS = ['django.contrib.auth.hashers.MD5PasswordHasher']
# Sem collectstatic nos testes: o armazenamento com versão no nome exige o manifesto gerado por ele.
STORAGES = {**STORAGES, 'staticfiles': {'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage'}}
# O cliente de testes fala HTTP; o redirecionamento para HTTPS é testado à parte.
SECURE_SSL_REDIRECT = False
# Nos testes o erro não vai para a tabela: quem testa o registro de erros liga o handler por conta própria.
LOGGING = {**LOGGING, 'root': {'handlers': ['console'], 'level': 'WARNING'}}
