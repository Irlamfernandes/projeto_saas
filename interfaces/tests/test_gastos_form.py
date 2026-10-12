from datetime import date
from decimal import Decimal
from django.http import QueryDict
from django.test import TestCase
from infrastructure.models import LojaModel, Produto
from interfaces.forms import CompraForm, DespesaForm, PerdaForm
from interfaces.forms.gastos_form import ERRO_ITEM, MAXIMO_DE_ITENS
from interfaces.views.comum import primeiro_erro


def compra(linhas, **campos):
    post = QueryDict(mutable=True)
    post.update({'data': '2026-09-10', **campos})
    for nome, indice in (('item_produto', 0), ('item_quantidade', 1), ('item_custo', 2)):
        post.setlist(nome, [linha[indice] for linha in linhas])
    return CompraForm(post)


class CompraFormTest(TestCase):

    def test_produto_com_variacao_vem_como_id_dois_pontos_variacao(self):
        form = compra([('1:7', '2', '3'), ('2', '1', '1')])
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual([(produto, variacao) for produto, _, _, variacao in form.parametros()['itens']], [(1, 7), (2, None)])
        self.assertFalse(compra([('1:', '2', '3')]).is_valid())

    def test_le_as_linhas_ignorando_as_vazias(self):
        form = compra([('1', '2,5', '10,5'), ('', '', ''), ('3', '1', '0')], fornecedor="Ceasa", atualizar_custo='1')

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros(), {
            'itens': [(1, Decimal('2.5'), Decimal('10.50'), None), (3, Decimal('1'), Decimal('0.00'), None)],
            'data': date(2026, 9, 10), 'fornecedor': "Ceasa", 'observacao': '', 'atualizar_custo': True,
        })

    def test_mensagens_de_erro(self):
        casos = {
            'sem produtos': ([('', '', '')], "Adicione pelo menos um produto à compra."),
            'texto': ([('1', 'dois', '3')], ERRO_ITEM),
            'infinito': ([('1', 'Infinity', '3')], ERRO_ITEM),
            'produto vazio': ([('', '2', '3')], ERRO_ITEM),
            'demais': ([('1', '1', '1')] * (MAXIMO_DE_ITENS + 1), ERRO_ITEM),
            'zero': ([('1', '0', '3')], "A quantidade precisa ser maior que zero e o custo não pode ser negativo."),
            'custo negativo': ([('1', '1', '-3')], "A quantidade precisa ser maior que zero e o custo não pode ser negativo."),
        }
        for nome, (linhas, mensagem) in casos.items():
            with self.subTest(nome):
                self.assertEqual(primeiro_erro(compra(linhas)), mensagem)

    def test_listas_de_tamanhos_diferentes(self):
        post = QueryDict('data=2026-09-10&item_produto=1&item_produto=2&item_quantidade=1&item_custo=1')
        self.assertEqual(primeiro_erro(CompraForm(post)), ERRO_ITEM)

    def test_data_obrigatoria(self):
        self.assertEqual(primeiro_erro(compra([('1', '1', '1')], data='')), "Informe a data.")


class DespesaEPerdaFormTest(TestCase):

    def test_despesa(self):
        form = DespesaForm({'data': '2026-09-10', 'categoria': 'Luz', 'valor': '150,40'})
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros()['valor'], Decimal('150.40'))
        self.assertEqual(primeiro_erro(DespesaForm({'data': '2026-09-10', 'valor': '0'})),
                         "Escolha ou escreva a categoria da despesa.")
        self.assertEqual(primeiro_erro(DespesaForm({'data': '2026-09-10', 'categoria': 'Luz', 'valor': '0'})),
                         "O valor deve ser maior que zero.")

    def test_perda_so_com_produto_da_loja(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        bolo = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=Decimal('1'))
        de_fora = Produto.objects.create(loja=LojaModel.objects.create(nome_loja="Outra"), nome="X", preco_venda=Decimal('1'))
        produtos = Produto.objects.filter(loja=loja)

        form = PerdaForm({'data': '2026-09-10', 'produto': bolo.pk, 'quantidade': '0,5', 'motivo': 'Venceu'}, produtos=produtos)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros(), {'produto_id': bolo.pk, 'variacao_id': None, 'quantidade': Decimal('0.5'),
                                             'data': date(2026, 9, 10), 'motivo': 'Venceu'})
        com_variacao = PerdaForm({'data': '2026-09-10', 'produto': f'{bolo.pk}:7', 'quantidade': '1', 'motivo': 'x'},
                                 produtos=produtos)
        self.assertTrue(com_variacao.is_valid(), com_variacao.errors)
        self.assertEqual(com_variacao.parametros()['variacao_id'], 7)
        for invalido in ('abc', f'{bolo.pk}:', ':3'):
            with self.subTest(invalido):
                form = PerdaForm({'data': '2026-09-10', 'produto': invalido, 'quantidade': '1', 'motivo': 'x'}, produtos=produtos)
                self.assertEqual(primeiro_erro(form), "Produto não encontrado nesta loja.")
        fora = PerdaForm({'data': '2026-09-10', 'produto': de_fora.pk, 'quantidade': '1', 'motivo': 'x'}, produtos=produtos)
        self.assertEqual(primeiro_erro(fora), "Produto não encontrado nesta loja.")
