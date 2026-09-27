from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from application.relatorios.vendas import (
    FluxoDoMes, Ponto, faturamento_por_dia, faturamento_por_mes, mais_vendidos, mapa_de_horarios, vendido_x_recebido,
)
from tests.apoio import CenarioDeLoja

AGORA = CenarioDeLoja.quando(2026, 3, 20, 15)


class AnalisesDeVendasTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.pao = self.c.produto("Pão francês", preco_venda='1.00')
        self.bolo = self.c.produto("Bolo", preco_venda='30.00')
        self.usuario = self.c.usuario()
        outra = CenarioDeLoja("Outra loja")
        outra.venda(CenarioDeLoja.quando(2026, 3, 20, 9), [(outra.produto("Intruso", preco_venda='999'), 1)])

    def test_faturamento_por_dia_preenche_dias_sem_venda(self):
        self.c.venda(CenarioDeLoja.quando(2026, 3, 18, 9), [(self.pao, 10)])
        self.c.venda(CenarioDeLoja.quando(2026, 3, 20, 23, 30), [(self.bolo, 1)])  # 02h30 UTC do dia 21

        pontos = faturamento_por_dia(self.usuario, dias=3, agora=AGORA)

        self.assertEqual(pontos, [
            Ponto(date(2026, 3, 18), Decimal('10.00')),
            Ponto(date(2026, 3, 19), Decimal('0.00')),
            Ponto(date(2026, 3, 20), Decimal('30.00')),
        ])

    def test_faturamento_por_mes(self):
        self.c.venda(CenarioDeLoja.quando(2026, 1, 31, 22), [(self.bolo, 1)])
        self.c.venda(CenarioDeLoja.quando(2026, 3, 1, 8), [(self.bolo, 2)])
        self.c.venda(CenarioDeLoja.quando(2025, 12, 31, 12), [(self.bolo, 5)])  # fora da janela

        pontos = faturamento_por_mes(self.usuario, meses=3, agora=AGORA)

        self.assertEqual(pontos, [
            Ponto(date(2026, 1, 1), Decimal('30.00')),
            Ponto(date(2026, 2, 1), Decimal('0.00')),
            Ponto(date(2026, 3, 1), Decimal('60.00')),
        ])

    def test_vendido_x_recebido(self):
        cliente = self.c.cliente("Ana")
        self.c.venda(CenarioDeLoja.quando(2026, 2, 10), [(self.bolo, 2)], cliente=cliente)
        self.c.pagamento(cliente, '25.00', CenarioDeLoja.quando(2026, 3, 5))
        self.c.venda(CenarioDeLoja.quando(2026, 2, 11), [(self.bolo, 5)])  # balcão: não entra

        fluxo = vendido_x_recebido(self.usuario, meses=2, agora=AGORA)

        self.assertEqual(fluxo, [
            FluxoDoMes(date(2026, 2, 1), Decimal('60.00'), Decimal('0.00')),
            FluxoDoMes(date(2026, 3, 1), Decimal('0.00'), Decimal('25.00')),
        ])

    def test_mais_vendidos_por_quantidade_no_periodo(self):
        self.c.venda(CenarioDeLoja.quando(2026, 3, 10), [(self.pao, 50), (self.bolo, 2)])
        self.c.venda(CenarioDeLoja.quando(2026, 3, 12), [(self.bolo, 1, '25.00')])
        self.c.venda(CenarioDeLoja.quando(2026, 2, 1), [(self.bolo, 100)])  # fora do período

        ranking = mais_vendidos(self.usuario, inicio=date(2026, 3, 1), fim=date(2026, 3, 20))

        self.assertEqual([(p.nome, p.quantidade, p.faturamento) for p in ranking], [
            ("Pão francês", 50, Decimal('50.00')),
            ("Bolo", 3, Decimal('85.00')),
        ])
        self.assertEqual(len(mais_vendidos(self.usuario, limite=1)), 1)
        self.assertEqual({p.unidade for p in ranking}, {'un'})

    def test_mapa_de_horarios(self):
        self.c.venda(CenarioDeLoja.quando(2026, 3, 16, 8, 10), [(self.bolo, 1)])   # segunda 8h
        self.c.venda(CenarioDeLoja.quando(2026, 3, 16, 8, 50), [(self.bolo, 1)])   # segunda 8h
        self.c.venda(CenarioDeLoja.quando(2026, 3, 14, 10), [(self.pao, 15)])      # sábado 10h

        mapa = mapa_de_horarios(self.usuario, dias=30, agora=AGORA)

        self.assertEqual(mapa.dias, ('Seg', 'Ter', 'Qua', 'Qui', 'Sex', 'Sáb', 'Dom'))
        self.assertEqual([hora for hora, _ in mapa.linhas], [8, 9, 10])
        segunda_8h = mapa.linhas[0][1][0]
        self.assertEqual((segunda_8h.total, segunda_8h.vendas, segunda_8h.intensidade), (Decimal('60.00'), 2, 1.0))
        sabado_10h = mapa.linhas[2][1][5]
        self.assertEqual((sabado_10h.dia, sabado_10h.intensidade), ('Sáb', 0.25))
        self.assertEqual((mapa.melhor.dia, mapa.melhor.hora), ('Seg', 8))

    def test_mapa_sem_vendas_usa_horario_comercial(self):
        mapa = mapa_de_horarios(self.usuario, agora=AGORA)
        self.assertEqual([hora for hora, _ in mapa.linhas], list(range(7, 21)))
        self.assertIsNone(mapa.melhor)

    def test_superusuario_ve_todas_as_lojas(self):
        superusuario = SimpleNamespace(is_superuser=True, loja=None)
        self.assertEqual(faturamento_por_dia(superusuario, dias=1, agora=AGORA)[0].valor, Decimal('999.00'))
