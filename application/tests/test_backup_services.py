import io
import json
import tempfile
import threading
from contextlib import redirect_stdout
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from application.auditoria.services import registrar_alteracao
from application.backup import services
from application.backup.services import (
    TRAVADO_POR, apagar_antigos, em_segundo_plano, fazer_backup, pedir_backup, registros_no_backup, restaurar,
)
from infrastructure.models import (
    Acao, Backup, Cliente, ConfiguracaoDeBackup, ErroDoSistema, ItemVenda, LojaModel, OrigemDoBackup, Produto, Venda,
)
from infrastructure.utils.backup_cripto import ChaveDeBackupInvalida, descriptografar
from tests.apoio import BackupsFalsos, CenarioDeLoja, ComPlanosIniciais

SENHA = 'senha-do-backup'
AGENDADO, MANUAL = OrigemDoBackup.AGENDADO, OrigemDoBackup.MANUAL


class Executor:
    """No lugar da thread: anota o que seria executado, sem executar."""

    def __init__(self):
        self.chamadas = []

    def __call__(self, funcao, *argumentos):
        self.chamadas.append((funcao, argumentos))


class PedirBackupTest(TestCase):

    def setUp(self):
        self.agora = timezone.now()
        self.executor = Executor()

    def _configurar(self, **campos):
        ConfiguracaoDeBackup.objects.update_or_create(pk=1, defaults=campos)

    def _pedir(self, origem=AGENDADO, agora=None):
        return pedir_backup(origem, agora or self.agora, self.executor)

    def test_agendado_desligado_nao_faz(self):
        self.assertEqual(self._pedir(), (False, "Backup automático desligado."))
        self.assertEqual(self.executor.chamadas, [])

    def test_agendado_antes_da_hora(self):
        self._configurar(ativo=True, a_cada=6, unidade='horas', ultimo_em=self.agora - timedelta(hours=1))
        iniciado, motivo = self._pedir()
        self.assertFalse(iniciado)
        proximo = timezone.localtime(self.agora + timedelta(hours=5))
        self.assertEqual(motivo, f"Ainda não é hora: o próximo é em {proximo:%d/%m/%Y %H:%M}.")

    def test_agendado_na_hora_marca_em_andamento_e_manda_fazer(self):
        self._configurar(ativo=True)
        self.assertEqual(self._pedir(), (True, "Backup iniciado."))
        self.assertEqual(self.executor.chamadas, [(fazer_backup, (AGENDADO,))])
        self.assertEqual(ConfiguracaoDeBackup.atual().em_andamento_desde, self.agora)

    def test_manual_faz_mesmo_desligado(self):
        self.assertTrue(self._pedir(MANUAL)[0])
        self.assertEqual(self.executor.chamadas, [(fazer_backup, (MANUAL,))])

    def test_nunca_dois_ao_mesmo_tempo(self):
        self._configurar(em_andamento_desde=self.agora - timedelta(minutes=10))
        self.assertEqual(self._pedir(MANUAL), (False, "Já tem um backup em andamento."))

    def test_backup_travado_ha_muito_tempo_libera(self):
        self._configurar(em_andamento_desde=self.agora - TRAVADO_POR)
        self.assertTrue(self._pedir(MANUAL)[0])

    def test_travado_libera_depois_de_2_horas(self):
        self._configurar(em_andamento_desde=self.agora - timedelta(hours=2))
        self.assertTrue(self._pedir(MANUAL)[0])

    def test_usa_a_hora_atual_e_a_thread_quando_nao_informadas(self):
        with patch.object(services, 'em_segundo_plano') as thread:
            self.assertTrue(pedir_backup(MANUAL)[0])
        thread.assert_called_once_with(fazer_backup, MANUAL)


class EmSegundoPlanoTest(TestCase):

    def test_roda_numa_thread_e_fecha_a_conexao_no_fim(self):
        feito = []

        class ThreadNaHora:
            def __init__(self, target, name):
                self.target, self.name = target, name

            def start(self):
                self.target()

        with patch.object(services.threading, 'Thread', ThreadNaHora), \
                patch.object(services, 'close_old_connections') as fechar:
            em_segundo_plano(feito.append, 'backup')
        self.assertEqual(feito, ['backup'])
        fechar.assert_called_once()

    def test_a_thread_se_chama_backup(self):
        """O nome aparece nos logs e nas ferramentas de diagnóstico do servidor."""
        nomes = []
        with patch.object(services, 'close_old_connections'):
            em_segundo_plano(lambda: nomes.append(threading.current_thread().name))
            for thread in threading.enumerate():
                if thread.name == 'backup':
                    thread.join()
        self.assertEqual(nomes, ['backup'])


@override_settings(BACKUP_CHAVE=SENHA)
class FazerBackupTest(ComPlanosIniciais, TestCase):

    def setUp(self):
        cenario = CenarioDeLoja("Padaria da Esquina")
        self.loja = cenario.loja
        self.cliente = cenario.cliente("Maria")
        pao = cenario.produto("Pão", estoque=50)
        cenario.venda(timezone.now(), [(pao, 3)], self.cliente)
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja)
        ErroDoSistema.objects.create(assinatura='x', tipo='ValueError')
        ConfiguracaoDeBackup.objects.create(pk=1, em_andamento_desde=timezone.now())
        self.armazenamento = BackupsFalsos()
        self.agora = timezone.now()
        pasta = tempfile.TemporaryDirectory()
        self.addCleanup(pasta.cleanup)
        self.tmp = Path(pasta.name)

    def _conteudo(self, backup):
        arquivo = self.tmp / backup.arquivo
        arquivo.write_bytes(self.armazenamento.arquivos[backup.arquivo])
        saida = io.BytesIO()
        descriptografar(arquivo, saida, SENHA)
        return json.loads(saida.getvalue())

    def test_guarda_o_arquivo_criptografado_e_registra(self):
        backup = fazer_backup(MANUAL, self.armazenamento, agora=self.agora)

        self.assertTrue(backup.sucesso)
        self.assertEqual(backup.arquivo, f"backup-{self.agora:%Y%m%d-%H%M%S}.json.gz.enc")
        self.assertEqual(backup.tamanho, len(self.armazenamento.arquivos[backup.arquivo]))
        self.assertEqual(backup.registros, registros_no_backup())
        self.assertIsNotNone(backup.duracao)
        config = ConfiguracaoDeBackup.atual()
        self.assertEqual((config.ultimo_em, config.em_andamento_desde), (self.agora, None))

        modelos = {item['model'] for item in self._conteudo(backup)}
        self.assertTrue({'infrastructure.lojamodel', 'infrastructure.usuariomodel', 'infrastructure.venda'} <= modelos)
        self.assertFalse(modelos & {'sessions.session', 'contenttypes.contenttype', 'infrastructure.errodosistema',
                                    'infrastructure.backup', 'infrastructure.configuracaodebackup'})

    def test_falha_vira_registro_e_erro_do_sistema(self):
        with self.assertLogs('application.backup.services', 'ERROR'):
            backup = fazer_backup(AGENDADO, BackupsFalsos(falhar_no_envio=True))
        self.assertFalse(backup.sucesso)
        self.assertEqual((backup.arquivo, backup.erro), ('', "Supabase fora do ar"))
        config = ConfiguracaoDeBackup.atual()
        self.assertEqual((config.ultimo_em, config.em_andamento_desde), (None, None))  # tenta de novo na próxima

    @override_settings(SUPABASE_URL='', SUPABASE_KEY='')
    def test_sem_supabase_configurado(self):
        with self.assertLogs('application.backup.services', 'ERROR'):
            backup = fazer_backup(MANUAL)
        self.assertIn("Credenciais do Supabase", backup.erro)

    def test_restaurar_num_banco_vazio_traz_tudo_de_volta(self):
        backup = fazer_backup(MANUAL, self.armazenamento)
        arquivo = self.tmp / 'baixado.enc'
        arquivo.write_bytes(self.armazenamento.arquivos[backup.arquivo])
        antes = (Venda.objects.count(), ItemVenda.objects.count(), Cliente.objects.count(), Produto.objects.count())

        ItemVenda.objects.all().delete()  # o item protege o produto: sai primeiro
        LojaModel.objects.all().delete()
        get_user_model().objects.all().delete()
        self.assertEqual(Venda.objects.count(), 0)

        restaurar(arquivo)
        self.assertEqual((Venda.objects.count(), ItemVenda.objects.count(), Cliente.objects.count(), Produto.objects.count()), antes)
        caixa = get_user_model().objects.get(username="caixa")
        self.assertEqual(caixa.loja.nome_loja, "Padaria da Esquina")
        self.assertTrue(caixa.check_password("x"))  # a senha (o hash) volta junto
        self.assertEqual(Venda.objects.get().cliente.nome, "Maria")

    def test_restaurar_com_senha_errada_nao_mexe_em_nada(self):
        backup = fazer_backup(MANUAL, self.armazenamento)
        arquivo = self.tmp / 'baixado.enc'
        arquivo.write_bytes(self.armazenamento.arquivos[backup.arquivo])
        with self.assertRaises(ChaveDeBackupInvalida):
            restaurar(arquivo, senha='errada')
        self.assertEqual(LojaModel.objects.count(), 1)

    def test_a_contagem_de_registros_e_a_do_arquivo_e_a_duracao_e_curta(self):
        backup = fazer_backup(MANUAL, self.armazenamento, agora=self.agora)
        self.assertEqual(backup.registros, len(self._conteudo(backup)))
        self.assertLess(backup.duracao, timedelta(minutes=1))

    def test_arquivo_portavel_usuario_pelo_nome_e_sem_id(self):
        """Chaves naturais: o arquivo não depende dos ids do banco de origem."""
        registrar_alteracao(loja=self.loja, usuario=self.usuario, acao=Acao.CLIENTE_CADASTRADO, descricao="Maria")
        conteudo = self._conteudo(fazer_backup(MANUAL, self.armazenamento, agora=self.agora))
        [usuario] = [item for item in conteudo if item['model'] == 'infrastructure.usuariomodel']
        [registro] = [item for item in conteudo if item['model'] == 'infrastructure.registrodealteracao']
        self.assertNotIn('pk', usuario)
        self.assertEqual(registro['fields']['usuario'], ["caixa"])

    def test_falha_guarda_o_comeco_do_erro_e_fica_no_log(self):
        armazenamento = BackupsFalsos()
        with patch.object(armazenamento, 'enviar', side_effect=RuntimeError("x" * 1500)), \
                self.assertLogs('application.backup.services', 'ERROR') as log:
            backup = fazer_backup(MANUAL, armazenamento, agora=self.agora)
        self.assertEqual((len(backup.erro), backup.arquivo), (1000, ''))
        self.assertLess(backup.duracao, timedelta(minutes=1))
        self.assertEqual(log.records[0].getMessage(), f"O backup backup-{self.agora:%Y%m%d-%H%M%S}.json.gz.enc falhou")

    def test_depois_de_dar_certo_apaga_as_copias_antigas(self):
        ConfiguracaoDeBackup.objects.filter(pk=1).update(manter=1)
        Backup.objects.create(criado_em=self.agora - timedelta(days=3), origem=AGENDADO, sucesso=True, arquivo='velho.enc')
        fazer_backup(MANUAL, self.armazenamento, agora=self.agora)
        self.assertEqual(self.armazenamento.removidos, ['velho.enc'])

    def test_restaurar_nao_escreve_nada_na_tela(self):
        backup = fazer_backup(MANUAL, self.armazenamento, agora=self.agora)
        arquivo = self.tmp / backup.arquivo
        arquivo.write_bytes(self.armazenamento.arquivos[backup.arquivo])
        saida = io.StringIO()
        with redirect_stdout(saida):
            restaurar(arquivo, SENHA)
        self.assertEqual(saida.getvalue(), '')


class EntraNoBackupTest(SimpleTestCase):

    def test_o_que_fica_de_fora(self):
        casos = {
            Cliente: True,
            ContentType: False,  # o app inteiro fica de fora
            Permission: False,   # só este modelo fica de fora; o resto do auth entra
            Group: True,
        }
        for modelo, entra in casos.items():
            with self.subTest(modelo.__name__):
                self.assertEqual(services._entra_no_backup(modelo), entra)
        proxy = SimpleNamespace(_meta=SimpleNamespace(app_label='infrastructure', label_lower='infrastructure.outro', proxy=True))
        self.assertFalse(services._entra_no_backup(proxy))  # proxy repetiria os dados do modelo de verdade


@override_settings(BACKUP_CHAVE=SENHA)
class ApagarAntigosTest(TestCase):

    def _backup(self, dias_atras, sucesso=True):
        return Backup.objects.create(
            criado_em=timezone.now() - timedelta(days=dias_atras), origem=AGENDADO, sucesso=sucesso,
            arquivo=f"b{dias_atras}.enc" if sucesso else '',
        )

    def test_guarda_so_as_mais_novas_e_limpa_falhas_velhas(self):
        ConfiguracaoDeBackup.objects.create(pk=1, manter=2)
        novo, meio, velho = self._backup(1), self._backup(2), self._backup(3)
        falha_recente, falha_velha = self._backup(1.5, sucesso=False), self._backup(10, sucesso=False)
        armazenamento = BackupsFalsos()

        apagar_antigos(armazenamento)

        self.assertEqual(armazenamento.removidos, ['b3.enc'])
        self.assertEqual(set(Backup.objects.all()), {novo, meio, falha_recente})
        self.assertNotIn(velho, Backup.objects.all())
        self.assertNotIn(falha_velha, Backup.objects.all())

    def test_se_nao_consegue_apagar_o_arquivo_mantem_o_registro(self):
        ConfiguracaoDeBackup.objects.create(pk=1, manter=1)
        self._backup(1)
        velho = self._backup(2)
        with self.assertLogs('application.backup.services', 'ERROR') as log:
            apagar_antigos(BackupsFalsos(falhar_ao_remover=('b2.enc',)))
        self.assertTrue(Backup.objects.filter(pk=velho.pk).exists())
        self.assertEqual(log.records[0].getMessage(), "Não deu para apagar o backup antigo b2.enc")

    def test_uma_copia_que_nao_sai_nao_impede_as_outras(self):
        ConfiguracaoDeBackup.objects.create(pk=1, manter=1)
        self._backup(1)
        self._backup(2)
        mais_velho = self._backup(3)
        armazenamento = BackupsFalsos(falhar_ao_remover=('b2.enc',))
        with self.assertLogs('application.backup.services', 'ERROR'):
            apagar_antigos(armazenamento)
        self.assertEqual(armazenamento.removidos, ['b3.enc'])
        self.assertFalse(Backup.objects.filter(pk=mais_velho.pk).exists())
