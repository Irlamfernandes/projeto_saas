"""Backup dos dados: quando fazer, como gerar e guardar o arquivo, apagar as cópias antigas e restaurar.

O arquivo é o `dumpdata` do Django (JSON), compactado e criptografado: não depende do `pg_dump` nem do banco —
restaura em Postgres ou SQLite, no Render, na AWS ou numa máquina qualquer. As fotos não entram: já ficam
guardadas no Storage, fora do banco.
"""
import logging
import tempfile
import threading
import time
from datetime import timedelta
from pathlib import Path
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.utils import timezone
from infrastructure.models import Backup, ConfiguracaoDeBackup, OrigemDoBackup
from infrastructure.utils.backup_cripto import criptografar, descriptografar
from infrastructure.utils.supabase_backups import BackupsNoSupabase
from infrastructure.utils.supabase_storage import StorageError

logger = logging.getLogger(__name__)

# Fica fora: o que o `migrate` recria sozinho (tipos e permissões), as sessões (basta entrar de novo) e o que é
# temporário ou do próprio backup.
FORA_DO_BACKUP = (
    'contenttypes', 'auth.permission', 'sessions', 'admin.logentry',
    'infrastructure.tentativasdelogin', 'infrastructure.errodosistema',
    'infrastructure.backup', 'infrastructure.configuracaodebackup',
)
# Um backup "em andamento" há mais tempo que isto morreu no meio (ex.: o servidor reiniciou): pode tentar de novo.
TRAVADO_POR = timedelta(hours=2)


def pedir_backup(origem, agora=None, executar=None):
    """Chamado pelo agendador (de hora em hora) e pelo botão do admin. Devolve (vai fazer?, motivo).

    O agendado só acontece se estiver ligado e na hora; o manual, sempre. Nunca dois ao mesmo tempo.
    """
    agora = agora or timezone.now()
    with transaction.atomic():
        config, _ = ConfiguracaoDeBackup.objects.select_for_update().get_or_create(pk=1)
        if config.em_andamento_desde and agora - config.em_andamento_desde < TRAVADO_POR:
            return False, "Já tem um backup em andamento."
        if origem == OrigemDoBackup.AGENDADO and not config.esta_na_hora(agora):
            if not config.ativo:
                return False, "Backup automático desligado."
            return False, f"Ainda não é hora: o próximo é em {timezone.localtime(config.proximo_em()):%d/%m/%Y %H:%M}."
        config.em_andamento_desde = agora
        config.save(update_fields=['em_andamento_desde'])
    (executar or em_segundo_plano)(fazer_backup, origem)
    return True, "Backup iniciado."


def em_segundo_plano(funcao, *argumentos):
    """Roda fora do pedido: o agendador (e quem clicou no admin) recebe a resposta na hora, sem esperar."""
    def rodar():
        try:
            funcao(*argumentos)
        finally:
            close_old_connections()
    threading.Thread(target=rodar, name='backup').start()


def fazer_backup(origem, armazenamento=None, senha=None, agora=None):
    inicio = agora or timezone.now()
    relogio = time.monotonic()
    nome = f"backup-{inicio:%Y%m%d-%H%M%S}.json.gz.enc"
    backup = Backup.objects.create(criado_em=inicio, origem=origem, arquivo=nome)
    try:
        armazenamento = armazenamento or BackupsNoSupabase.from_settings()
        with tempfile.TemporaryDirectory() as pasta:
            dados, cifrado = Path(pasta) / 'dados.json', Path(pasta) / nome
            call_command('dumpdata', exclude=list(FORA_DO_BACKUP), natural_foreign=True, natural_primary=True,
                         output=str(dados), verbosity=0)
            with open(dados, 'rb') as entrada, open(cifrado, 'wb') as saida:
                criptografar(entrada, saida, senha if senha is not None else settings.BACKUP_CHAVE)
            armazenamento.enviar(cifrado, nome)
            tamanho = cifrado.stat().st_size
    except Exception as erro:  # qualquer falha vira registro (e aparece em "Erros do sistema")
        logger.exception("O backup %s falhou", nome)
        Backup.objects.filter(pk=backup.pk).update(
            arquivo='', erro=str(erro)[:1000], duracao=timedelta(seconds=time.monotonic() - relogio),
        )
        ConfiguracaoDeBackup.objects.filter(pk=1).update(em_andamento_desde=None)
        backup.refresh_from_db()
        return backup

    Backup.objects.filter(pk=backup.pk).update(
        sucesso=True, tamanho=tamanho, registros=registros_no_backup(),
        duracao=timedelta(seconds=time.monotonic() - relogio),
    )
    ConfiguracaoDeBackup.objects.filter(pk=1).update(em_andamento_desde=None, ultimo_em=inicio)
    apagar_antigos(armazenamento)
    backup.refresh_from_db()
    return backup


def _entra_no_backup(modelo):
    meta = modelo._meta
    return meta.app_label not in FORA_DO_BACKUP and meta.label_lower not in FORA_DO_BACKUP and not meta.proxy


def registros_no_backup():
    return sum(modelo._default_manager.count() for modelo in apps.get_models() if _entra_no_backup(modelo))


def apagar_antigos(armazenamento):
    """Mantém só as `manter` cópias mais novas que deram certo; as falhas mais velhas que elas saem da lista.

    Só é chamado logo depois de um backup que deu certo: sempre existe ao menos uma cópia guardada.
    """
    manter = ConfiguracaoDeBackup.atual().manter
    for antigo in list(Backup.objects.filter(sucesso=True)[manter:]):
        try:
            armazenamento.remover(antigo.arquivo)
        except StorageError:
            logger.exception("Não deu para apagar o backup antigo %s", antigo.arquivo)
            continue
        antigo.delete()
    mais_antigo = Backup.objects.filter(sucesso=True).order_by('criado_em').values_list('criado_em', flat=True).first()
    Backup.objects.filter(sucesso=False, criado_em__lt=mais_antigo).delete()


def restaurar(caminho, senha=None):
    """Coloca de volta os dados de um arquivo de backup. Use num banco novo, já com o `migrate` rodado."""
    with tempfile.TemporaryDirectory() as pasta:
        dados = Path(pasta) / 'dados.json'
        with open(dados, 'wb') as saida:
            descriptografar(caminho, saida, senha if senha is not None else settings.BACKUP_CHAVE)
        with transaction.atomic():
            call_command('loaddata', str(dados), verbosity=0)
