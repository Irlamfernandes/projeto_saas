from datetime import date
from decimal import Decimal
from django.test import TestCase
from application.relatorios.clientes import clientes_sumidos, idade_das_dividas, melhores_clientes
from tests.apoio import CenarioDeLoja

AGORA = CenarioDeLoja.quando(2026, 3, 20, 15)


class AnalisesDeClientesTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.bolo = self.c.produto("Bolo", preco_venda='50')

    def test_idade_das_dividas(self):
        recente = self.c.cliente("Recente")
        self.c.venda(CenarioDeLoja.quando(2026, 3, 1), [(self.bolo, 2)], cliente=recente)
        self.c.pagamento(recente, '20', CenarioDeLoja.quando(2026, 3, 15))
        antigo = self.c.cliente("Antigo")
        self.c.venda(CenarioDeLoja.quando(2025, 11, 1), [(self.bolo, 1)], cliente=antigo)
        em_dia = self.c.cliente("Em dia")
        self.c.venda(CenarioDeLoja.quando(2026, 3, 1), [(self.bolo, 1)], cliente=em_dia)
        self.c.pagamento(em_dia, '50', CenarioDeLoja.quando(2026, 3, 2))

        dividas = idade_das_dividas(self.c.usuario(), agora=AGORA)

        self.assertEqual([(d.cliente.nome, d.saldo, d.dias_sem_pagar) for d in dividas.devedores], [
            ("Antigo", Decimal('50.00'), 139), ("Recente", Decimal('80.00'), 5),
        ])
        self.assertEqual([(f.rotulo, f.clientes, f.total) for f in dividas.faixas], [
            ("Até 30 dias", 1, Decimal('80.00')), ("31 a 60 dias", 0, Decimal('0.00')),
            ("61 a 90 dias", 0, Decimal('0.00')), ("Mais de 90 dias", 1, Decimal('50.00')),
        ])
        self.assertEqual((dividas.total, dividas.acima_de(60)), (Decimal('130.00'), 1))

    def test_melhores_clientes_no_periodo(self):
        ana, bia = self.c.cliente("Ana"), self.c.cliente("Bia")
        self.c.venda(CenarioDeLoja.quando(2026, 3, 5), [(self.bolo, 1)], cliente=ana)
        self.c.venda(CenarioDeLoja.quando(2026, 3, 6), [(self.bolo, 1)], cliente=ana)
        self.c.venda(CenarioDeLoja.quando(2026, 3, 7), [(self.bolo, 3)], cliente=bia)
        self.c.venda(CenarioDeLoja.quando(2026, 1, 7), [(self.bolo, 9)], cliente=ana)  # fora

        ranking = melhores_clientes(self.c.usuario(), inicio=date(2026, 3, 1), fim=date(2026, 3, 31))

        self.assertEqual([(r.cliente.nome, r.total, r.compras) for r in ranking], [
            ("Bia", Decimal('150.00'), 1), ("Ana", Decimal('100.00'), 2),
        ])
        self.assertEqual(len(melhores_clientes(self.c.usuario())), 2)

    def test_clientes_sumidos(self):
        sumido, ativo = self.c.cliente("Sumido"), self.c.cliente("Ativo")
        self.c.cliente("Nunca comprou")
        self.c.venda(CenarioDeLoja.quando(2025, 12, 1), [(self.bolo, 4)], cliente=sumido)
        self.c.venda(CenarioDeLoja.quando(2026, 3, 10), [(self.bolo, 1)], cliente=ativo)

        sumidos = clientes_sumidos(self.c.usuario(), dias=60, agora=AGORA)

        self.assertEqual([(s.cliente.nome, s.total, s.dias_sem_comprar) for s in sumidos], [("Sumido", Decimal('200.00'), 109)])
