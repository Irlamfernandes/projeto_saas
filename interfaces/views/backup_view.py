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
    enviado = request.headers.get('Authorization', '').removeprefix('Bearer ')
    return bool(token) and hmac.compare_digest(enviado.encode(), token.encode())


@csrf_exempt  # NOSONAR: quem chama é o agendador (sem navegador, sem cookie de sessão); a proteção é o token
@require_POST
def backup_agendado_view(request):
    if not _autorizado(request):
        raise Http404
    iniciado, motivo = pedir_backup(OrigemDoBackup.AGENDADO)
    return JsonResponse({'iniciado': iniciado, 'motivo': motivo}, status=202 if iniciado else 200)
