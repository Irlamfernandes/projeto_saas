from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
from django.test import TestCase
from infrastructure.models import Backup, ConfiguracaoDeBackup, UnidadeDoIntervalo
from infrastructure.models.backup import somar_intervalo

FUSO = ZoneInfo('America/Sao_Paulo')
BASE = datetime(2026, 1, 31, 10, 7, tzinfo=FUSO)


class SomarIntervaloTest(TestCase):

    def test_horas_e_dias(self):
        self.assertEqual(somar_intervalo(BASE, 6, UnidadeDoIntervalo.HORAS), BASE + timedelta(hours=6))
        self.assertEqual(somar_intervalo(BASE, 2, UnidadeDoIntervalo.DIAS), BASE + timedelta(days=2))

    def test_meses_respeitam_o_fim_do_mes_e_a_virada_do_ano(self):
        self.assertEqual(somar_intervalo(BASE, 1, UnidadeDoIntervalo.MESES).date(), datetime(2026, 2, 28).date())
        self.assertEqual(somar_intervalo(BASE.replace(year=2028), 1, UnidadeDoIntervalo.MESES).day, 29)  # bissexto
        self.assertEqual(somar_intervalo(BASE, 12, UnidadeDoIntervalo.MESES), BASE.replace(year=2027))
        dezembro = datetime(2026, 12, 15, tzinfo=FUSO)
        self.assertEqual(somar_intervalo(dezembro, 1, UnidadeDoIntervalo.MESES), datetime(2027, 1, 15, tzinfo=FUSO))


class ConfiguracaoDeBackupTest(TestCase):

    def test_uma_so_configuracao_desligada_por_padrao(self):
        config = ConfiguracaoDeBackup.atual()
        self.assertEqual(ConfiguracaoDeBackup.atual().pk, config.pk)
        self.assertEqual((config.ativo, config.a_cada, config.unidade, config.manter), (False, 1, 'dias', 30))
        self.assertEqual(str(config), 'Configuração de backup')

    def test_quando_e_hora(self):
        config = ConfiguracaoDeBackup(a_cada=6, unidade=UnidadeDoIntervalo.HORAS)
        self.assertFalse(config.esta_na_hora(BASE))
        self.assertIsNone(config.proximo_em())

        config.ativo = True
        self.assertTrue(config.esta_na_hora(BASE))  # nunca feito: já
        self.assertIsNone(config.proximo_em())

        config.ultimo_em = BASE
        self.assertEqual(config.proximo_em(), BASE + timedelta(hours=6))
        self.assertFalse(config.esta_na_hora(BASE + timedelta(hours=5)))
        self.assertTrue(config.esta_na_hora(BASE + timedelta(hours=6, minutes=-30)))  # o agendador chegou um pouco antes
        self.assertFalse(config.esta_na_hora(BASE + timedelta(hours=6, minutes=-31)))
        self.assertTrue(config.esta_na_hora(BASE + timedelta(hours=7)))


class BackupTest(TestCase):

    def test_nome(self):
        self.assertEqual(str(Backup(criado_em=BASE, arquivo='backup-1.json.gz.enc')), 'backup-1.json.gz.enc')
        self.assertEqual(str(Backup(criado_em=BASE)), 'Backup de 31/01/2026 10:07')

    def test_nome_no_horario_de_brasilia(self):
        self.assertEqual(str(Backup(criado_em=datetime(2026, 2, 1, 1, 7, tzinfo=UTC))), 'Backup de 31/01/2026 22:07')
