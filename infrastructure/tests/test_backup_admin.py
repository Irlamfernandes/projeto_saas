from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from infrastructure.models import Backup, ConfiguracaoDeBackup, OrigemDoBackup
from tests.apoio import BackupsFalsos

LISTA = '/admin/infrastructure/backup/'
CONFIGURACAO = '/admin/infrastructure/configuracaodebackup/'


def _backup(sucesso=True, **campos):
    return Backup.objects.create(
        criado_em=timezone.now(), origem=OrigemDoBackup.AGENDADO, sucesso=sucesso,
        arquivo='backup-1.json.gz.enc' if sucesso else '', tamanho=1536, **campos,
    )


class BackupAdminTest(TestCase):

    def setUp(self):
        self.dono = get_user_model().objects.create_superuser(username="dono", password="x", deve_trocar_senha=False)
        self.client.force_login(self.dono)

    def test_configuracao_e_uma_tela_so(self):
        resposta = self.client.get(CONFIGURACAO)
        self.assertRedirects(resposta, f'{CONFIGURACAO}1/change/')
        tela = self.client.get(f'{CONFIGURACAO}1/change/')
        self.assertContains(tela, "Desligado")
        self.assertEqual(self.client.get(f'{CONFIGURACAO}add/').status_code, 403)

    def test_proximo_backup(self):
        config = ConfiguracaoDeBackup.objects.create(pk=1, ativo=True)
        self.assertContains(self.client.get(f'{CONFIGURACAO}1/change/'), "Na próxima chamada do agendador")
        config.ultimo_em = timezone.now()
        config.save()
        proximo = timezone.localtime(config.proximo_em())
        self.assertContains(self.client.get(f'{CONFIGURACAO}1/change/'), f"{proximo:%d/%m/%Y %H:%M}")

    def test_salvar_a_configuracao_volta_para_a_lista(self):
        ConfiguracaoDeBackup.atual()
        resposta = self.client.post(f'{CONFIGURACAO}1/change/', {'ativo': 'on', 'a_cada': 6, 'unidade': 'horas', 'manter': 10})
        self.assertRedirects(resposta, LISTA, fetch_redirect_response=False)
        config = ConfiguracaoDeBackup.atual()
        self.assertEqual((config.ativo, config.a_cada, config.unidade, config.manter), (True, 6, 'horas', 10))
        self.assertContains(self.client.get(LISTA), "Configuração de backup salva.")

    def test_lista(self):
        guardado = _backup()
        _backup(sucesso=False, erro="Supabase fora do ar")
        lista = self.client.get(LISTA)
        self.assertContains(lista, "Guardado")
        self.assertContains(lista, "Falhou")
        self.assertContains(lista, "1,5\xa0KB")  # espaço que não quebra a linha
        self.assertContains(lista, "Supabase fora do ar")
        self.assertContains(lista, f'href="/admin/infrastructure/backup/{guardado.pk}/baixar/"')
        self.assertEqual(self.client.get(f'{LISTA}add/').status_code, 403)

    def test_fazer_agora(self):
        with patch('infrastructure.admin.backup_admin.pedir_backup', return_value=(True, "Backup iniciado.")) as pedir:
            resposta = self.client.get(f'{LISTA}fazer-agora/', follow=True)
        pedir.assert_called_once_with('manual')
        self.assertContains(resposta, "Backup iniciado. Em instantes")
        with patch('infrastructure.admin.backup_admin.pedir_backup', return_value=(False, "Já tem um backup em andamento.")):
            self.assertContains(self.client.get(f'{LISTA}fazer-agora/', follow=True), "Já tem um backup em andamento.")

    def test_botao_configurar(self):
        self.assertRedirects(self.client.get(f'{LISTA}configurar/'), CONFIGURACAO, target_status_code=302)

    def test_baixar(self):
        backup = _backup()
        falsos = BackupsFalsos()
        falsos.arquivos[backup.arquivo] = b'conteudo-cifrado'
        with patch('infrastructure.admin.backup_admin.BackupsNoSupabase.from_settings', return_value=falsos):
            resposta = self.client.get(f'{LISTA}{backup.pk}/baixar/')
        self.assertEqual(b''.join(resposta.streaming_content), b'conteudo-cifrado')
        self.assertEqual(resposta['Content-Disposition'], 'attachment; filename="backup-1.json.gz.enc"')

    def test_baixar_com_supabase_fora(self):
        backup = _backup()
        with patch('infrastructure.admin.backup_admin.BackupsNoSupabase.from_settings',
                   return_value=BackupsFalsos(falhar_no_envio=True)) as fonte:
            fonte.return_value.baixar = lambda nome, destino: fonte.return_value.enviar(None, nome)
            resposta = self.client.get(f'{LISTA}{backup.pk}/baixar/', follow=True)
        self.assertContains(resposta, "Não deu para baixar o backup: Supabase fora do ar")

    def test_backup_que_falhou_nao_tem_o_que_baixar(self):
        self.assertEqual(self.client.get(f'{LISTA}{_backup(sucesso=False).pk}/baixar/').status_code, 404)


class SoOSuperusuarioTest(TestCase):

    def test_equipe_sem_ser_dono_nao_ve_nem_baixa(self):
        equipe = get_user_model().objects.create_user(username="equipe", password="x", is_staff=True, deve_trocar_senha=False)
        self.client.force_login(equipe)
        backup = _backup()
        self.assertEqual(self.client.get(LISTA).status_code, 403)
        self.assertEqual(self.client.get(f'{CONFIGURACAO}1/change/').status_code, 403)
        self.assertEqual(self.client.get(f'{LISTA}{backup.pk}/baixar/').status_code, 404)


@override_settings(BACKUP_CHAVE='senha')
class ComandosTest(TestCase):

    def _falsos(self, **opcoes):
        return patch('application.backup.services.BackupsNoSupabase.from_settings', return_value=BackupsFalsos(**opcoes))

    def test_fazer_backup(self):
        with self._falsos():
            call_command('fazer_backup', stdout=(saida := _Saida()))
        self.assertIn("guardado", saida.texto)
        self.assertTrue(Backup.objects.get().sucesso)

    def test_fazer_backup_que_falha(self):
        with self._falsos(falhar_no_envio=True), self.assertLogs('application.backup.services', 'ERROR'), \
                self.assertRaisesMessage(CommandError, "O backup falhou: Supabase fora do ar"):
            call_command('fazer_backup')

    def test_agendado_fora_da_hora(self):
        call_command('fazer_backup', '--agendado', stdout=(saida := _Saida()))
        self.assertEqual(saida.texto, "Backup automático desligado.\n")
        self.assertFalse(Backup.objects.exists())

    def test_restaurar(self):
        falsos = BackupsFalsos()
        with patch('application.backup.services.BackupsNoSupabase.from_settings', return_value=falsos):
            call_command('fazer_backup', stdout=_Saida())
        arquivo = self._arquivo(next(iter(falsos.arquivos.values())))
        call_command('restaurar_backup', str(arquivo), stdout=(saida := _Saida()))
        self.assertIn("Dados restaurados.", saida.texto)
        with self.assertRaisesMessage(CommandError, "Senha errada"):
            call_command('restaurar_backup', str(arquivo), '--chave', 'errada')
        with self.assertRaises(CommandError):
            call_command('restaurar_backup', str(arquivo.with_name('nao-existe')))

    def _arquivo(self, conteudo):
        import tempfile
        from pathlib import Path
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        arquivo = Path(pasta.name) / 'backup.enc'
        arquivo.write_bytes(conteudo)
        return arquivo


class _Saida:
    def __init__(self):
        self.texto = ''

    def write(self, texto):
        self.texto += texto

    def flush(self):
        """Exigido pelo OutputWrapper do Django."""


class ConfiguracaoTravadaTest(TestCase):

    def test_backup_travado_ha_pouco_bloqueia_o_comando(self):
        ConfiguracaoDeBackup.objects.create(pk=1, em_andamento_desde=timezone.now() - timedelta(minutes=5))
        call_command('fazer_backup', stdout=(saida := _Saida()))
        self.assertEqual(saida.texto, "Já tem um backup em andamento.\n")
