"""Endereço que o agendador chama de hora em hora (.github/workflows/backup.yml ou o cron de um servidor).

Protegido por BACKUP_TOKEN no cabeçalho Authorization. Sem token configurado, ou com token errado, responde
404: para quem não sabe o token, o endereço nem existe.
"""
import hmac
from django.conf import settings
from django.http import Http404, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from application.backup.services import pedir_backup
from infrastructure.models import OrigemDoBackup


def _autorizado(request):
    token = settings.BACKUP_TOKEN
    enviado = request.headers.get('Authorization')
    if not token or not enviado:
        return False
    return hmac.compare_digest(enviado.removeprefix('Bearer ').encode(), token.encode())


# Sem CSRF de propósito: quem chama é o agendador (sem navegador, sem cookie de sessão, então não há sessão a
# forjar). A proteção é o BACKUP_TOKEN no cabeçalho, comparado em tempo constante.
@csrf_exempt
@require_POST
def backup_agendado_view(request):
    if not _autorizado(request):
        raise Http404
    iniciado, motivo = pedir_backup(OrigemDoBackup.AGENDADO)
    return JsonResponse({'iniciado': iniciado, 'motivo': motivo}, status=202 if iniciado else 200)
