from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import patch
from django.test import SimpleTestCase, TestCase
from application.assinatura.situacao import SituacaoDoPlano, plano_vencido, situacao_do_plano
from infrastructure.models import LojaModel

HOJE = date(2026, 10, 20)


def situacao(dias):
    return SituacaoDoPlano(vencimento=HOJE + timedelta(days=dias), dias_restantes=dias)


class SituacaoDoPlanoTest(SimpleTestCase):

    def test_nivel_do_aviso_sobe_conforme_o_vencimento_chega(self):
        casos = {30: '', 8: '', 7: 'info', 4: 'info', 3: 'alerta', 2: 'alerta', 1: 'critico', 0: 'critico', -1: 'critico'}
        for dias, nivel in casos.items():
            with self.subTest(dias=dias):
                self.assertEqual(situacao(dias).nivel, nivel)

    def test_textos_dos_avisos(self):
        self.assertEqual(situacao(10).aviso, '')
        self.assertEqual(situacao(5).aviso, "Seu plano vence em 5 dias (25/10/2026). Renove para não ter o uso limitado.")
        self.assertEqual(situacao(1).aviso, "Seu plano vence amanhã (21/10/2026). Renove para não ter o uso limitado.")
        self.assertEqual(situacao(0).aviso, "Seu plano vence hoje. Renove para continuar usando o sistema por completo.")
        self.assertIn("Seu plano venceu em 19/10/2026. Você ainda pode consultar tudo", situacao(-1).aviso)

    def test_vence_no_fim_do_dia(self):
        self.assertFalse(situacao(0).vencido)
        self.assertTrue(situacao(-1).vencido)

    def test_calcula_os_dias_a_partir_de_hoje(self):
        loja = SimpleNamespace(vencimento=date(2026, 10, 25))
        self.assertEqual(situacao_do_plano(loja, hoje=HOJE).dias_restantes, 5)
        self.assertIsNone(situacao_do_plano(None))

    @patch('application.assinatura.situacao.timezone.localdate', return_value=HOJE)
    def test_plano_vencido(self, _):
        vencida = SimpleNamespace(is_superuser=False, loja=SimpleNamespace(vencimento=HOJE - timedelta(days=1)))
        em_dia = SimpleNamespace(is_superuser=False, loja=SimpleNamespace(vencimento=HOJE))
        self.assertTrue(plano_vencido(vencida))
        self.assertFalse(plano_vencido(em_dia))
        self.assertFalse(plano_vencido(SimpleNamespace(is_superuser=True, loja=vencida.loja)))
        self.assertFalse(plano_vencido(SimpleNamespace(is_superuser=False, loja=None)))


class TesteGratisTest(TestCase):

    @patch('infrastructure.models.loja_model.timezone.localdate', return_value=HOJE)
    def test_loja_nova_ganha_30_dias_gratis(self, _):
        loja = LojaModel.objects.create(nome_loja="Nova")
        self.assertEqual(loja.vencimento, date(2026, 11, 19))
