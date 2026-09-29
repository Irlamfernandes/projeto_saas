from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo
from django.test import SimpleTestCase
from application.relatorios.indicadores import Comparacao
from application.relatorios.periodos import dias_entre, meses_ate, mesmo_momento_no_mes_anterior, primeiro_dia_do_mes


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
