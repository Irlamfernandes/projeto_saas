from decimal import Decimal
from django.test import SimpleTestCase, TestCase
from infrastructure.models import Cliente, LojaModel
from interfaces.forms import BuscaClientesForm, ClienteForm, PagamentoForm
from interfaces.views.comum import primeiro_erro


class ClienteFormTest(TestCase):

    def _form(self, **dados):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        return ClienteForm({'nome': 'Ana', **dados}, instance=Cliente(loja=loja))

    def test_campos_opcionais_vazios_ficam_em_branco_e_nao_nulos(self):
        """Regressão: campos vazios viravam None e o banco recusava (HTTP 500)."""
        form = self._form(telefone='', email='', endereco='')

        self.assertTrue(form.is_valid(), form.errors)
        cliente = form.save()
        self.assertEqual((cliente.telefone, cliente.email, cliente.endereco), ('', '', ''))

    def test_mensagens_de_erro(self):
        casos = {
            'sem nome': ({'nome': ' '}, "O nome do cliente é obrigatório."),
            'nome longo': ({'nome': 'a' * 256}, "O nome pode ter no máximo 255 caracteres."),
            'telefone longo': ({'telefone': '1' * 21}, "O telefone pode ter no máximo 20 caracteres."),
            'email inválido': ({'email': 'ana@'}, "Informe um e-mail válido."),
        }
        for caso, (dados, mensagem) in casos.items():
            with self.subTest(caso):
                form = self._form(**dados)
                self.assertFalse(form.is_valid())
                self.assertEqual(primeiro_erro(form), mensagem)


class PagamentoFormTest(SimpleTestCase):

    def test_aceita_virgula_como_separador_decimal(self):
        form = PagamentoForm({'valor': '75,50', 'forma_pagamento': 'pix', 'observacao': ' parcela '})

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.parametros(), {'valor': Decimal('75.50'), 'forma_pagamento': 'pix', 'observacao': 'parcela'})

    def test_mensagens_de_erro(self):
        casos = {
            'vazio': ({'valor': ''}, "Informe o valor do pagamento."),
            'texto': ({'valor': 'abc'}, "O valor informado para o pagamento é inválido."),
            'zero': ({'valor': '0'}, "O valor do pagamento deve ser maior que zero."),
            'negativo': ({'valor': '-10'}, "O valor do pagamento deve ser maior que zero."),
            'centavos demais': ({'valor': '1.999'}, "Use no máximo duas casas decimais."),
            'alto demais': ({'valor': '123456789'}, "O valor do pagamento é alto demais."),
            'observação longa': (
                {'valor': '1', 'forma_pagamento': 'pix', 'observacao': 'a' * 256},
                "A observação excede o limite máximo de 255 caracteres.",
            ),
            'sem forma': ({'valor': '1'}, "Informe como foi pago."),
            'forma inválida': ({'valor': '1', 'forma_pagamento': 'cheque'}, "Forma de pagamento inválida."),
        }
        for caso, (dados, mensagem) in casos.items():
            with self.subTest(caso):
                form = PagamentoForm(dados)
                self.assertFalse(form.is_valid())
                self.assertEqual(primeiro_erro(form), mensagem)


class BuscaClientesFormTest(SimpleTestCase):

    def test_termo_longo_demais(self):
        form = BuscaClientesForm({'q': 'a' * 101})
        self.assertFalse(form.is_valid())
        self.assertEqual(primeiro_erro(form), "O termo de busca é muito longo.")
