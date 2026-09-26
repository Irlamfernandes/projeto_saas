from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase, TestCase
from application.relatorios.indicadores import Comparacao, indicadores_do_painel
from application.relatorios.periodos import dias_entre, meses_ate, mesmo_momento_no_mes_anterior, primeiro_dia_do_mes
from tests.apoio import CenarioDeLoja

AGORA = CenarioDeLoja.quando(2026, 3, 20, 15)  # sexta-feira


class IndicadoresDoPainelTest(TestCase):

    def test_compara_com_o_periodo_anterior_ate_o_mesmo_horario(self):
        c = CenarioDeLoja()
        bolo = c.produto("Bolo", preco_venda='10')
        c.venda(CenarioDeLoja.quando(2026, 3, 20, 9), [(bolo, 12)])      # hoje
        c.venda(CenarioDeLoja.quando(2026, 3, 13, 10), [(bolo, 10)])     # sexta passada, antes das 15h
        c.venda(CenarioDeLoja.quando(2026, 3, 13, 18), [(bolo, 50)])     # sexta passada, depois das 15h: fora
        c.venda(CenarioDeLoja.quando(2026, 2, 5), [(bolo, 20)])          # fevereiro até dia 20
        cliente = c.cliente("Devedor antigo")
        c.venda(CenarioDeLoja.quando(2025, 12, 1), [(bolo, 3)], cliente=cliente)

        indicadores = indicadores_do_painel(c.usuario(), agora=AGORA)

        self.assertEqual((indicadores.hoje.atual, indicadores.hoje.anterior, indicadores.hoje.variacao), (Decimal('120.00'), Decimal('100.00'), 20))
        self.assertEqual((indicadores.sete_dias.atual, indicadores.sete_dias.anterior), (Decimal('120.00'), Decimal('100.00')))
        self.assertEqual((indicadores.mes.atual, indicadores.mes.anterior), (Decimal('720.00'), Decimal('200.00')))
        self.assertEqual((indicadores.a_receber, indicadores.clientes_devendo, indicadores.devendo_ha_muito_tempo), (Decimal('30.00'), 1, 1))


class ComparacaoTest(SimpleTestCase):

    def test_variacao(self):
        caiu = Comparacao(Decimal('90'), Decimal('100'))
        self.assertEqual((caiu.variacao, caiu.subiu, caiu.variacao_absoluta), (-10, False, 10))
        sem_base = Comparacao(Decimal('90'), Decimal('0'))
        self.assertEqual((sem_base.variacao, sem_base.subiu, sem_base.variacao_absoluta), (None, True, 0))


class PeriodosTest(SimpleTestCase):

    def test_utilitarios_de_data(self):
        self.assertEqual(dias_entre(date(2026, 2, 27), date(2026, 3, 1)), [date(2026, 2, 27), date(2026, 2, 28), date(2026, 3, 1)])
        self.assertEqual(primeiro_dia_do_mes(date(2026, 1, 15), 2), date(2025, 11, 1))
        self.assertEqual(meses_ate(date(2026, 2, 10), 3), [date(2025, 12, 1), date(2026, 1, 1), date(2026, 2, 1)])

    def test_mesmo_momento_no_mes_anterior_ajusta_o_dia(self):
        sp = ZoneInfo('America/Sao_Paulo')
        self.assertEqual(mesmo_momento_no_mes_anterior(datetime(2026, 3, 31, 10, tzinfo=sp)), datetime(2026, 2, 28, 10, tzinfo=sp))
        self.assertEqual(mesmo_momento_no_mes_anterior(datetime(2026, 1, 15, 10, tzinfo=sp)), datetime(2025, 12, 15, 10, tzinfo=sp))
