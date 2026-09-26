from datetime import date
from django.test import SimpleTestCase
from interfaces.forms import LimiteEstoqueForm, PeriodoForm


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
