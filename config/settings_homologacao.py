"""Homologação na sua máquina (`make homologar`): igual à produção — DEBUG desligado, gunicorn, estáticos
comprimidos, Postgres — só que em HTTP, para abrir no navegador e no celular pela rede local.

Nunca use no Render: lá o HTTPS existe e estas exceções abririam mão dele.
"""
import os

from config import settings as producao

# Começa com todas as configurações da produção (as de nome em maiúsculas, como o Django lê) e troca só as abaixo.
globals().update({nome: valor for nome, valor in vars(producao).items() if nome.isupper()})

# Sem HTTPS na máquina local: com os cookies seguros e o redirecionamento da produção, o login não funcionaria.
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
SECURE_HSTS_SECONDS = 0

# O celular abre pelo IP da máquina (ex.: http://192.168.0.10:8000); o formulário precisa aceitar essa origem.
PORTA = os.environ.get('PORTA', '8000')
CSRF_TRUSTED_ORIGINS = [*producao.CSRF_TRUSTED_ORIGINS, *(f'http://{host}:{PORTA}' for host in producao.ALLOWED_HOSTS)]
