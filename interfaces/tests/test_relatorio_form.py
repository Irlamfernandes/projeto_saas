from datetime import date
from django.test import SimpleTestCase
from interfaces.forms import LimiteEstoqueForm, PeriodoForm, escolher_dias
from tests.apoio import CenarioDeLoja


class PeriodoFormTest(SimpleTestCase):

    def test_intervalo_valido(self):
        form = PeriodoForm({'data_inicio': '2026-01-10', 'data_fim': '2026-01-31'})
        self.assertEqual(form.intervalo(), (date(2026, 1, 10), date(2026, 1, 31)))

    def test_datas_ausentes_ou_invalidas_viram_none(self):
        self.assertEqual(PeriodoForm({}).intervalo(), (None, None))
        self.assertEqual(PeriodoForm({'data_inicio': 'abc', 'data_fim': '2026-01-31'}).intervalo(), (None, date(2026, 1, 31)))


class LimiteEstoqueFormTest(SimpleTestCase):

    def test_limite(self):
        casos = {'': 5, '20': 20, '0': 0, 'abc': 5, '-1': 5, '999999': 5}
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(LimiteEstoqueForm({'limite_estoque': valor}).limite(), esperado)
        self.assertEqual(LimiteEstoqueForm({}).limite(), 5)


class IntervaloPadraoTest(SimpleTestCase):

    def test_sem_datas_usa_os_ultimos_dias(self):
        agora = CenarioDeLoja.quando(2026, 3, 20, 23, 30)
        self.assertEqual(PeriodoForm({}).intervalo_ou_ultimos(30, agora), (date(2026, 2, 19), date(2026, 3, 20)))

    def test_datas_informadas_prevalecem(self):
        form = PeriodoForm({'data_inicio': '2026-01-01'})
        self.assertEqual(form.intervalo_ou_ultimos(30), (date(2026, 1, 1), None))


class EscolherDiasTest(SimpleTestCase):

    def test_escolher_dias(self):
        self.assertEqual(escolher_dias('90', (30, 90), 30), 90)
        self.assertEqual(escolher_dias('45', (30, 90), 30), 30)
        self.assertEqual(escolher_dias('abc', (30, 90), 30), 30)
        self.assertEqual(escolher_dias(None, (30, 90), 30), 30)
