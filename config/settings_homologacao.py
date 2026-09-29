"""Homologação na sua máquina (`make homologar`): igual à produção — DEBUG desligado, gunicorn, estáticos
comprimidos, Postgres — só que em HTTP, para abrir no navegador e no celular pela rede local.

Nunca use no Render: lá o HTTPS existe e estas exceções abririam mão dele.
"""
import os

from config.settings import *  # noqa: F403

# Sem HTTPS na máquina local: com os cookies seguros e o redirecionamento da produção, o login não funcionaria.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# O celular abre pelo IP da máquina (ex.: http://192.168.0.10:8000); o formulário precisa aceitar essa origem.
PORTA = os.environ.get('PORTA', '8000')
CSRF_TRUSTED_ORIGINS = [*CSRF_TRUSTED_ORIGINS, *(f'http://{host}:{PORTA}' for host in ALLOWED_HOSTS)]  # noqa: F405 # NOSONAR
