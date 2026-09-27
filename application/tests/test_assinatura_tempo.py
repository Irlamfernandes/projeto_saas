from datetime import date
from django.test import SimpleTestCase
from application.assinatura.tempo import novo_vencimento, somar_meses

HOJE = date(2026, 9, 26)


class NovoVencimentoTest(SimpleTestCase):

    def test_plano_em_dias_soma_dias(self):
        self.assertEqual(novo_vencimento(date(2026, 10, 1), HOJE, 30, 'dias'), date(2026, 10, 31))

    def test_plano_em_meses_soma_meses_de_calendario(self):
        self.assertEqual(novo_vencimento(date(2026, 10, 1), HOJE, 6, 'meses'), date(2027, 4, 1))
        self.assertEqual(novo_vencimento(date(2026, 10, 1), HOJE, 12, 'meses'), date(2027, 10, 1))

    def test_renovar_antes_de_vencer_nao_perde_dias(self):
        self.assertEqual(novo_vencimento(date(2026, 10, 20), HOJE, 30, 'dias'), date(2026, 11, 19))

    def test_ja_vencido_conta_a_partir_de_hoje(self):
        self.assertEqual(novo_vencimento(date(2026, 8, 1), HOJE, 30, 'dias'), date(2026, 10, 26))


class SomarMesesTest(SimpleTestCase):

    def test_dia_que_nao_existe_no_mes_vira_o_ultimo_dia(self):
        casos = {
            (date(2026, 8, 31), 6): date(2027, 2, 28),
            (date(2027, 8, 31), 6): date(2028, 2, 29),  # ano bissexto
            (date(2026, 1, 31), 3): date(2026, 4, 30),
            (date(2026, 11, 15), 2): date(2027, 1, 15),  # virada de ano
            (date(2026, 12, 31), 12): date(2027, 12, 31),
        }
        for (data, meses), esperado in casos.items():
            with self.subTest(data=data, meses=meses):
                self.assertEqual(somar_meses(data, meses), esperado)
