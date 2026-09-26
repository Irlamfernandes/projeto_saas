from decimal import Decimal
from django.test import TestCase
from infrastructure.models import Cliente, LojaModel
from interfaces.forms import EditarVendaForm, NovaVendaForm
from interfaces.views.comum import primeiro_erro


class VendaFormTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Cliente A")
        self.clientes = Cliente.objects.filter(loja=self.loja)

    def _nova(self, **dados):
        base = {'cliente': self.cliente.pk, 'produto': 'AR01', 'quantidade': '2'}
        return NovaVendaForm({**base, **dados}, clientes=self.clientes)

    def test_parametros_da_nova_venda(self):
        form = self._nova(valor_pago='10.50', observacoes='  obs  ')

        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros(), {
            'cliente': self.cliente, 'termo_produto': 'AR01', 'quantidade': 2,
            'observacoes': 'obs', 'valor_pago': Decimal('10.50'),
        })

    def test_valor_pago_em_branco_vira_zero(self):
        form = self._nova(valor_pago='')
        self.assertTrue(form.is_valid())
        self.assertEqual(form.parametros()['valor_pago'], Decimal('0'))

    def test_mensagens_de_erro(self):
        casos = {
            'quantidade zero': ({'quantidade': '0'}, "A quantidade deve ser maior que zero."),
            'quantidade texto': ({'quantidade': 'abc'}, "Quantidade inválida informada."),
            'valor negativo': ({'valor_pago': '-1'}, "O valor pago não pode ser negativo."),
            'valor texto': ({'valor_pago': 'abc'}, "Valor pago inicial inválido."),
            'sem produto': ({'produto': ' '}, "Informe o produto."),
            'sem cliente': ({'cliente': ''}, "Selecione o cliente."),
        }
        for caso, (dados, mensagem) in casos.items():
            with self.subTest(caso):
                form = self._nova(**dados)
                self.assertFalse(form.is_valid())
                self.assertEqual(primeiro_erro(form), mensagem)

    def test_cliente_fora_do_queryset_permitido_e_rejeitado(self):
        outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        estranho = Cliente.objects.create(loja=outra_loja, nome="Estranho")

        form = self._nova(cliente=estranho.pk)

        self.assertFalse(form.is_valid())
        self.assertEqual(primeiro_erro(form), "Cliente selecionado não foi encontrado.")

    def test_edicao_aceita_venda_sem_cliente(self):
        form = EditarVendaForm(
            {'cliente': '', 'produto': 'AR01', 'quantidade': '1'}, clientes=self.clientes,
        )

        self.assertTrue(form.is_valid())
        self.assertIsNone(form.parametros()['cliente'])
        self.assertNotIn('valor_pago', form.parametros())
