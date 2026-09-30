"""Backups no admin (grupo Sistema), só para o superusuário: o arquivo tem os dados de todas as lojas.

- Configuração: liga/desliga, de quanto em quanto tempo e quantas cópias guardar (uma tela só, sem lista).
- Backups: as cópias feitas, com botão para fazer agora e link para baixar cada uma.
"""
import tempfile
from django.contrib import admin, messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect
from django.template.defaultfilters import filesizeformat
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import action, display
from application.backup.services import pedir_backup
from infrastructure.models import Backup, ConfiguracaoDeBackup, OrigemDoBackup
from infrastructure.utils.supabase_backups import BackupsNoSupabase
from infrastructure.utils.supabase_storage import StorageError


class SoSuperusuario:
    def has_module_permission(self, request):
        return request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


def _data(momento):
    return f"{timezone.localtime(momento):%d/%m/%Y %H:%M}" if momento else '—'


@admin.register(ConfiguracaoDeBackup)
class ConfiguracaoDeBackupAdmin(SoSuperusuario, ModelAdmin):
    fields = ('ativo', 'a_cada', 'unidade', 'manter', 'ultimo', 'proximo')
    readonly_fields = ('ultimo', 'proximo')

    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser

    def changelist_view(self, request, extra_context=None):
        """Não há lista: é uma configuração só."""
        return redirect('admin:infrastructure_configuracaodebackup_change', ConfiguracaoDeBackup.atual().pk)

    def response_change(self, request, obj):
        messages.success(request, "Configuração de backup salva.")
        return redirect('admin:infrastructure_backup_changelist')

    @display(description="Último backup que deu certo")
    def ultimo(self, config):
        return _data(config.ultimo_em)

    @display(description="Próximo backup automático")
    def proximo(self, config):
        if not config.ativo:
            return "Desligado"
        return _data(config.proximo_em()) if config.ultimo_em else "Na próxima chamada do agendador"


@admin.register(Backup)
class BackupAdmin(SoSuperusuario, ModelAdmin):
    list_display = ('criado_em', 'situacao', 'origem', 'tamanho_legivel', 'registros', 'duracao', 'baixar')
    list_filter = ('sucesso', 'origem')
    actions_list = ('fazer_agora', 'configurar')
    readonly_fields = ('criado_em', 'origem', 'arquivo', 'tamanho', 'registros', 'duracao', 'sucesso', 'erro')

    def has_change_permission(self, request, obj=None):
        return False

    def get_urls(self):
        baixar = path('<int:pk>/baixar/', self.admin_site.admin_view(self.baixar_view), name='infrastructure_backup_baixar')
        return [baixar, *super().get_urls()]

    @display(description="Situação", ordering='sucesso', label={'Guardado': 'success', 'Falhou': 'danger'})
    def situacao(self, backup):
        return 'Guardado' if backup.sucesso else 'Falhou'

    @display(description="Tamanho", ordering='tamanho')
    def tamanho_legivel(self, backup):
        if not backup.sucesso:
            return '—'
        return filesizeformat(backup.tamanho)

    @display(description="Arquivo")
    def baixar(self, backup):
        if not backup.sucesso:
            return backup.erro[:120]
        return format_html('<a class="text-primary-600" href="{}">Baixar</a>',
                           reverse('admin:infrastructure_backup_baixar', args=[backup.pk]))

    def baixar_view(self, request, pk):
        """Entrega o arquivo como está guardado (criptografado): só abre com a BACKUP_CHAVE."""
        if not request.user.is_superuser:
            raise Http404
        backup = get_object_or_404(Backup, pk=pk, sucesso=True)
        # Sem `with`: quem fecha é o FileResponse, depois de enviar; fechado, o arquivo temporário some do disco.
        arquivo = tempfile.TemporaryFile()  # noqa: SIM115
        try:
            BackupsNoSupabase.from_settings().baixar(backup.arquivo, arquivo)
        except StorageError as erro:
            arquivo.close()
            messages.error(request, f"Não deu para baixar o backup: {erro}")
            return redirect('admin:infrastructure_backup_changelist')
        arquivo.seek(0)
        return FileResponse(arquivo, as_attachment=True, filename=backup.arquivo, content_type='application/octet-stream')

    @action(description="Fazer backup agora", icon='backup', url_path='fazer-agora')
    def fazer_agora(self, request):
        iniciado, motivo = pedir_backup(OrigemDoBackup.MANUAL)
        if iniciado:
            messages.success(request, "Backup iniciado. Em instantes ele aparece aqui (atualize a página).")
        else:
            messages.warning(request, motivo)
        return redirect('admin:infrastructure_backup_changelist')

    @action(description="Configurar", icon='settings', url_path='configurar')
    def configurar(self, request):
        return redirect('admin:infrastructure_configuracaodebackup_changelist')
