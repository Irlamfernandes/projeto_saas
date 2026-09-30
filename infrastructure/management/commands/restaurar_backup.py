"""`python manage.py restaurar_backup arquivo.json.gz.enc`: coloca de volta os dados de um backup.

Use num banco NOVO, já com `python manage.py migrate`. A senha é a BACKUP_CHAVE do ambiente (ou --chave).
O arquivo sai do admin (Sistema → Backups → Baixar).
"""
from django.core.management.base import BaseCommand, CommandError
from application.backup.services import restaurar
from infrastructure.utils.backup_cripto import ChaveDeBackupInvalida


class Command(BaseCommand):
    help = "Restaura os dados de um arquivo de backup num banco novo (já com o migrate rodado)."

    def add_arguments(self, parser):
        parser.add_argument('arquivo')
        parser.add_argument('--chave', help="senha do backup (padrão: BACKUP_CHAVE do ambiente)")

    def handle(self, *args, arquivo, chave=None, **opcoes):
        try:
            restaurar(arquivo, chave)
        except (ChaveDeBackupInvalida, FileNotFoundError) as erro:
            raise CommandError(str(erro)) from erro
        self.stdout.write(self.style.SUCCESS("Dados restaurados."))
