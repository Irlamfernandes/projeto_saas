from decimal import Decimal
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation
from interfaces.templatetags.formatacao import moeda, moeda_absoluta


class MoedaTest(SimpleTestCase):

    def test_saida_identica_ao_floatformat_em_pt_br(self):
        """`moeda` substitui `|default:0|floatformat:2` por desempenho; a saída não pode mudar."""
        template = Template('{% load formatacao %}{{ v|default:0|floatformat:2 }}|{{ v|moeda }}')
        valores = [
            Decimal('1234.5'), Decimal('-20'), Decimal('2.345'), Decimal('2.355'), Decimal('-0.001'),
            Decimal('1E+3'), 0, None, '', 7, 3.14159, 'abc',
        ]
        with translation.override('pt-br'):
            for valor in valores:
                with self.subTest(valor=valor):
                    floatformat, nosso = template.render(Context({'v': valor})).split('|')
                    self.assertEqual(nosso, floatformat)

    def test_moeda_absoluta(self):
        self.assertEqual(moeda_absoluta(Decimal('-20.5')), '20,50')
        self.assertEqual(moeda_absoluta(Decimal('7')), '7,00')
        self.assertEqual(moeda_absoluta(None), '0,00')
        self.assertEqual(moeda_absoluta('abc'), '')

    def test_valores_diretos(self):
        self.assertEqual(moeda(Decimal('199.99')), '199,99')
        self.assertEqual(moeda(Decimal('-0.004')), '0,00')
