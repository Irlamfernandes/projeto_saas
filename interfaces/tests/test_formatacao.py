from decimal import Decimal
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation
from interfaces.templatetags.formatacao import intensidade, moeda, moeda_absoluta


class MoedaTest(SimpleTestCase):

    def test_mesmo_arredondamento_do_floatformat_mais_separador_de_milhar(self):
        """`moeda` substituiu `|default:0|floatformat:2` por desempenho e passou a separar milhares."""
        casos = {
            Decimal('1234.5'): '1.234,50', Decimal('-20'): '-20,00', Decimal('2.345'): '2,35',
            Decimal('2.355'): '2,36', Decimal('-0.001'): '0,00', Decimal('1E+3'): '1.000,00',
            Decimal('1234567.891'): '1.234.567,89', Decimal('-45523.3'): '-45.523,30',
            0: '0,00', None: '0,00', '': '0,00', 7: '7,00', 3.14159: '3,14', 'abc': '',
        }
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(moeda(valor), esperado)

    def test_arredondamento_igual_ao_floatformat_abaixo_de_mil(self):
        template = Template('{% load formatacao %}{{ v|default:0|floatformat:2 }}|{{ v|moeda }}')
        with translation.override('pt-br'):
            for valor in (Decimal('2.345'), Decimal('999.995'), Decimal('-0.005'), Decimal('0.125')):
                with self.subTest(valor=valor):
                    floatformat, nosso = template.render(Context({'v': valor})).split('|')
                    self.assertEqual(nosso.replace('.', ''), floatformat.replace('.', ''))

    def test_moeda_absoluta(self):
        self.assertEqual(moeda_absoluta(Decimal('-20.5')), '20,50')
        self.assertEqual(moeda_absoluta(Decimal('-1500')), '1.500,00')
        self.assertEqual(moeda_absoluta(Decimal('7')), '7,00')
        self.assertEqual(moeda_absoluta(None), '0,00')
        self.assertEqual(moeda_absoluta('abc'), '')

    def test_valores_diretos(self):
        self.assertEqual(moeda(Decimal('199.99')), '199,99')
        self.assertEqual(moeda(Decimal('-0.004')), '0,00')


class IntensidadeTest(SimpleTestCase):

    def test_escala_do_mapa_de_calor(self):
        self.assertEqual([intensidade(v) for v in (0, 0.5, 1, None)], [15, 58, 100, 15])
