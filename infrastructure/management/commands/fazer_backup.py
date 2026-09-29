"""`python manage.py fazer_backup`: faz um backup agora (para o cron de um servidor próprio, ou à mão).

Com --agendado, segue a configuração do admin (só faz se estiver ligado e na hora), igual ao /interno/backup/.
"""
from django.core.management.base import BaseCommand, CommandError
from application.backup.services import pedir_backup
from infrastructure.models import OrigemDoBackup


class Command(BaseCommand):
    help = "Faz um backup dos dados agora (ou, com --agendado, só se estiver na hora)."

    def add_arguments(self, parser):
        parser.add_argument('--agendado', action='store_true', help="respeita liga/desliga e intervalo do admin")

    def handle(self, *args, agendado=False, **opcoes):
        origem = OrigemDoBackup.AGENDADO if agendado else OrigemDoBackup.MANUAL
        vai, motivo = pedir_backup(origem, executar=self._aqui_mesmo)
        if not vai:
            self.stdout.write(motivo)
            return
        if not self.backup.sucesso:
            raise CommandError(f"O backup falhou: {self.backup.erro}")
        self.stdout.write(self.style.SUCCESS(f"Backup {self.backup.arquivo} guardado ({self.backup.tamanho} bytes)."))

    def _aqui_mesmo(self, funcao, *argumentos):
        """No terminal não há por que rodar em segundo plano: o comando espera o backup terminar."""
        self.backup = funcao(*argumentos)
