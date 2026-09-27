from datetime import date
from decimal import Decimal
from django.http import QueryDict
from django.test import TestCase
from infrastructure.models import Cliente, FormaDePagamento, LojaModel, PagamentoCliente, Venda
from interfaces.forms import CancelarVendaForm, EditarVendaForm, NovaVendaForm
from interfaces.forms.venda_form import MAXIMO_DE_ITENS
from interfaces.views.comum import primeiro_erro


def dados_do_post(itens=((1, 2),), **campos):
    """Monta o POST como o navegador envia: listas paralelas item_produto e item_quantidade."""
    post = QueryDict(mutable=True)
    for campo, valor in campos.items():
        post[campo] = valor
    post.setlist('item_produto', [str(produto) for produto, _ in itens])
    post.setlist('item_quantidade', [str(quantidade) for _, quantidade in itens])
    return post


class NovaVendaFormTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Cliente A")
        self.clientes = Cliente.objects.filter(loja=self.loja)

    def _form(self, itens=((1, 2),), **campos):
        return NovaVendaForm(dados_do_post(itens, **campos), clientes=self.clientes)

    def test_parametros_com_cliente_e_varios_itens(self):
        form = self._form(((1, 2), (5, 1)), cliente=self.cliente.pk, valor_pago='10.50', forma_pagamento='pix', observacoes='  obs  ')

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros(), {
            'cliente': self.cliente, 'itens': [(1, 2), (5, 1)], 'forma_pagamento': 'pix',
            'observacoes': 'obs', 'valor_pago': Decimal('10.50'), 'vencimentos': [],
        })

    def test_vencimento_vira_lista_de_vencimentos(self):
        form = self._form(cliente=self.cliente.pk, vencimento='2026-10-15')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros()['vencimentos'], [date(2026, 10, 15)])

    def test_cliente_vazio_e_venda_de_balcao(self):
        form = self._form(cliente='', forma_pagamento='dinheiro')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertIsNone(form.parametros()['cliente'])

    def test_balcao_ignora_o_valor_pago(self):
        form = self._form(cliente='', forma_pagamento='dinheiro', valor_pago='3')
        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros()['valor_pago'], Decimal('0'))

    def test_valor_pago_em_branco_vira_zero(self):
        form = self._form(cliente=self.cliente.pk, valor_pago='')
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros()['valor_pago'], Decimal('0'))

    def test_fiado_sem_pagamento_dispensa_a_forma(self):
        self.assertTrue(self._form(cliente=self.cliente.pk).is_valid())

    def test_mensagens_de_erro(self):
        casos = {
            'sem itens': ({'itens': ()}, "Adicione pelo menos um produto à venda."),
            'quantidade zero': ({'itens': ((1, 0),)}, "A quantidade de cada produto deve ser maior que zero."),
            'quantidade texto': ({'itens': ((1, 'abc'),)}, "Um dos itens da venda é inválido. Remova-o e adicione de novo."),
            'produto texto': ({'itens': (('pão', 1),)}, "Um dos itens da venda é inválido. Remova-o e adicione de novo."),
            'itens demais': ({'itens': tuple((i, 1) for i in range(MAXIMO_DE_ITENS + 1))}, "Um dos itens da venda é inválido. Remova-o e adicione de novo."),
            'balcão sem forma': ({'cliente': ''}, "Informe como foi pago."),
            'pagou sem forma': ({'cliente': 'CLIENTE', 'valor_pago': '5'}, "Informe como foi pago."),
            'forma inválida': ({'cliente': '', 'forma_pagamento': 'cheque'}, "Forma de pagamento inválida."),
            'valor negativo': ({'cliente': 'CLIENTE', 'valor_pago': '-1'}, "O valor pago não pode ser negativo."),
            'valor texto': ({'cliente': 'CLIENTE', 'valor_pago': 'abc'}, "Valor pago inicial inválido."),
            'cliente de fora': ({'cliente': '999999'}, "Cliente selecionado não foi encontrado."),
            'vencimento inválido': ({'cliente': 'CLIENTE', 'vencimento': '31/31/2026'}, "Data de vencimento inválida."),
        }
        for nome, (dados, mensagem) in casos.items():
            with self.subTest(nome):
                dados = dict(dados)
                if dados.get('cliente') == 'CLIENTE':
                    dados['cliente'] = self.cliente.pk
                form = self._form(**dados)
                self.assertFalse(form.is_valid())
                self.assertEqual(primeiro_erro(form), mensagem)

    def test_itens_com_listas_de_tamanhos_diferentes_sao_recusados(self):
        post = dados_do_post(((1, 1),), cliente=self.cliente.pk)
        post.setlist('item_quantidade', ['1', '2'])
        form = NovaVendaForm(post, clientes=self.clientes)
        self.assertFalse(form.is_valid())


class EditarVendaFormTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Cliente A")
        self.clientes = Cliente.objects.filter(loja=self.loja)
        self.venda = Venda.objects.create(loja=self.loja, cliente=self.cliente)

    def _form(self, **campos):
        return EditarVendaForm(dados_do_post(**campos), clientes=self.clientes, venda=self.venda)

    def test_fiado_sem_pagamento_no_ato_dispensa_a_forma(self):
        form = self._form(cliente=self.cliente.pk)
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros()['itens'], [(1, 2)])

    def test_com_pagamento_no_ato_pede_a_forma(self):
        PagamentoCliente.objects.create(loja=self.loja, cliente=self.cliente, venda=self.venda, valor=Decimal('1'))
        form = self._form(cliente=self.cliente.pk)
        self.assertFalse(form.is_valid())
        self.assertEqual(primeiro_erro(form), "Informe como foi pago.")

    def test_balcao_pede_a_forma(self):
        form = self._form(cliente='')
        self.assertFalse(form.is_valid())
        self.assertTrue(self._form(cliente='', forma_pagamento=FormaDePagamento.PIX).is_valid())


class CancelarVendaFormTest(TestCase):

    def test_exige_senha_e_motivo(self):
        form = CancelarVendaForm({'senha': '', 'motivo': ''})
        self.assertFalse(form.is_valid())
        self.assertEqual(form.errors['senha'], ["Digite sua senha para confirmar."])
        self.assertEqual(form.errors['motivo'], ["Conte o motivo do cancelamento."])

    def test_senha_nao_perde_espacos(self):
        form = CancelarVendaForm({'senha': ' com espaço ', 'motivo': 'erro'})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros(), {'senha': ' com espaço ', 'motivo': 'erro'})
