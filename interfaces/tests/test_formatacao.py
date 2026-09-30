from decimal import Decimal
from django.template import Context, Template
from django.test import SimpleTestCase
from django.utils import translation
from infrastructure.utils.formatacao import chave_alfabetica, com_opcoes, item, numero, quantidade
from interfaces.templatetags.formatacao import (
    intensidade, maximo_de_opcoes, moeda, moeda_absoluta, numero_simples, passo_da_quantidade, unidades_de_medida,
    valores_da_opcao,
)


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


class QuantidadeTest(SimpleTestCase):

    def test_numero_sem_zeros_sobrando(self):
        casos = {Decimal('2.500'): '2,5', Decimal('3.000'): '3', Decimal('1234.5'): '1.234,5', 10: '10',
                 None: '0', Decimal('0.0004'): '0', 'abc': ''}
        for valor, esperado in casos.items():
            with self.subTest(valor=valor):
                self.assertEqual(numero(valor), esperado)

    def test_quantidade_e_item_com_unidade(self):
        self.assertEqual(quantidade(Decimal('0.350'), 'kg'), '0,35 kg')
        self.assertEqual(quantidade(3, 'un'), '3 un.')
        self.assertEqual(item(Decimal('2'), 'un', 'Bolo'), '2× Bolo')
        self.assertEqual(item(2, None, 'Bolo'), '2× Bolo')
        self.assertEqual(item(Decimal('1.5'), 'l', 'Suco'), '1,5 L Suco')

    def test_nome_com_as_opcoes_escolhidas(self):
        self.assertEqual(com_opcoes('Camiseta', [{'nome': 'Tamanho', 'valor': 'G'}, {'nome': 'Cor', 'valor': 'Azul'}]),
                         'Camiseta (G, Azul)')
        self.assertEqual([com_opcoes('Bolo', vazio) for vazio in ([], None)], ['Bolo', 'Bolo'])

    def test_opcoes_no_formulario_do_produto(self):
        opcao = {'nome': 'Tamanho', 'valores': [{'nome': 'P', 'acrescimo': '0.00'}, {'nome': 'G', 'acrescimo': '1234.50'}]}
        self.assertEqual(valores_da_opcao(opcao), 'P\nG + 1234,50')
        self.assertEqual(maximo_de_opcoes(), 5)

    def test_filtros_do_formulario_de_estoque(self):
        self.assertEqual(numero_simples(Decimal('2.500')), '2.5')
        self.assertEqual(numero_simples(None), '0')
        self.assertEqual([passo_da_quantidade(c) for c in (0, 3, None)], ['1', '0.001', '1'])
        quilo = next(u for u in unidades_de_medida() if u['valor'] == 'kg')
        self.assertEqual(quilo, {'valor': 'kg', 'rotulo': 'Quilo (kg)', 'sigla': 'kg', 'casas': 3})

    def test_filtros_de_quantidade_no_template(self):
        from types import SimpleNamespace
        item_de_venda = SimpleNamespace(quantidade=Decimal('0.250'), produto=SimpleNamespace(unidade='kg', nome='Queijo'))
        com_opcoes_escolhidas = SimpleNamespace(quantidade=Decimal('1'), produto=SimpleNamespace(unidade='un', nome='Bolo'),
                                                opcoes=[{'nome': 'Sabor', 'valor': 'Coco'}])
        texto = Template(
            "{% load formatacao %}{{ q|quantidade:'kg' }} | {{ item|descricao_do_item }} | {{ outro|descricao_do_item }}",
        ).render(Context({'q': Decimal('1.500'), 'item': item_de_venda, 'outro': com_opcoes_escolhidas}))
        self.assertEqual(texto, '1,5 kg | 0,25 kg Queijo | 1× Bolo (Coco)')


class ChaveAlfabeticaTest(SimpleTestCase):

    def test_ordena_como_no_dicionario_sem_separar_acentos_nem_maiusculas(self):
        palavras = ['Transporte', 'água', 'Aluguel', 'Ágil', 'ÁRVORE', 'avião']
        self.assertEqual(sorted(palavras, key=chave_alfabetica), ['Ágil', 'água', 'Aluguel', 'ÁRVORE', 'avião', 'Transporte'])
        self.assertEqual(chave_alfabetica('Água-Açaí'), 'agua-acai')
