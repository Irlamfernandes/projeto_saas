from datetime import date
from decimal import Decimal
from django.test import SimpleTestCase
from django.utils import translation
from application.relatorios.vendas import FluxoDoMes, Ponto
from interfaces import graficos


class ApresentacaoDeGraficosTest(SimpleTestCase):

    def setUp(self):
        translation.activate('pt-br')
        self.addCleanup(translation.deactivate)

    def test_diario(self):
        dados = graficos.diario([Ponto(date(2026, 3, 20), Decimal('10.50'))])
        self.assertEqual(dados, {
            'rotulos': ['20/03'],
            'detalhes': ['Sexta-feira, 20 de março'],
            'series': [{'nome': 'Faturamento', 'valores': [10.5], 'cor': 'marca'}],
        })

    def test_mensal(self):
        dados = graficos.mensal([Ponto(date(2026, 3, 1), Decimal('7'))], nome='Vendas')
        self.assertEqual((dados['rotulos'], dados['detalhes'], dados['series'][0]['nome']), (['mar/26'], ['Março de 2026'], 'Vendas'))

    def test_vendido_x_recebido_usa_as_duas_cores_validadas(self):
        dados = graficos.vendido_x_recebido([FluxoDoMes(date(2026, 2, 1), Decimal('60'), Decimal('25'))])
        self.assertEqual([(s['nome'], s['valores'], s['cor']) for s in dados['series']], [
            ('Vendido na caderneta', [60.0], 'marca'), ('Recebido', [25.0], 'destaque'),
        ])

    def test_ranking(self):
        self.assertEqual(graficos.ranking(['Pão'], [Decimal('3')], 'Unidades'), {
            'rotulos': ['Pão'], 'series': [{'nome': 'Unidades', 'valores': [3.0], 'cor': 'marca'}],
        })
