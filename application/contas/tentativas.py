"""Proteção contra quem tenta adivinhar senhas: depois de 5 senhas erradas seguidas, o usuário fica
15 minutos sem conseguir entrar (no site e no admin). Acertar a senha zera a contagem.

Conta pelo nome digitado, não pelo IP: atrás do proxy do Render e da Cloudflare, o IP pode ser forjado.
Erros antigos (mais de 15 minutos sem novas tentativas) não se acumulam.
"""
import math
from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from infrastructure.models import TentativasDeLogin

MAXIMO_DE_FALHAS = 5
TEMPO_DE_BLOQUEIO = timedelta(minutes=15)
# Nomes que só erraram há muito tempo saem da tabela (inclusive os inventados por quem tenta adivinhar).
GUARDAR_POR = timedelta(days=1)


def _chave(usuario):
    return (usuario or '').strip().casefold()[:150]


def minutos_bloqueado(usuario, agora=None):
    """Quantos minutos faltam para o usuário poder tentar de novo (0 = liberado)."""
    agora = agora or timezone.now()
    bloqueado_ate = (
        TentativasDeLogin.objects.filter(usuario=_chave(usuario), bloqueado_ate__gt=agora)
        .values_list('bloqueado_ate', flat=True).first()
    )
    return math.ceil((bloqueado_ate - agora).total_seconds() / 60) if bloqueado_ate else 0


@transaction.atomic
def registrar_falha(usuario, agora=None):
    agora = agora or timezone.now()
    TentativasDeLogin.objects.filter(ultima_falha__lt=agora - GUARDAR_POR).delete()
    tentativas, _ = TentativasDeLogin.objects.select_for_update().get_or_create(
        usuario=_chave(usuario), defaults={'ultima_falha': agora},
    )
    if tentativas.ultima_falha < agora - TEMPO_DE_BLOQUEIO:
        tentativas.falhas = 0
    tentativas.falhas += 1
    tentativas.ultima_falha = agora
    if tentativas.falhas >= MAXIMO_DE_FALHAS:
        tentativas.falhas = 0
        tentativas.bloqueado_ate = agora + TEMPO_DE_BLOQUEIO
    tentativas.save()


def esquecer_falhas(usuario):
    TentativasDeLogin.objects.filter(usuario=_chave(usuario)).delete()
