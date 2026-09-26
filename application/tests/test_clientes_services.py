from decimal import Decimal
from django.test import TestCase
from application.clientes.exceptions import ClienteSemLoja
from application.clientes.services import cadastrar_cliente, registrar_pagamento
from infrastructure.models import Cliente, LojaModel


class ClientesServicesTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")

    def test_cadastrar_cliente(self):
        cliente = cadastrar_cliente(Cliente(loja=self.loja, nome="Ana"))
        self.assertEqual(Cliente.objects.get(), cliente)

    def test_cliente_sem_loja_e_recusado(self):
        with self.assertRaises(ClienteSemLoja):
            cadastrar_cliente(Cliente(nome="Ana"))
        self.assertFalse(Cliente.objects.exists())

    def test_registrar_pagamento_abate_o_saldo_na_loja_do_cliente(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")

        pagamento = registrar_pagamento(cliente, valor=Decimal('30.00'), observacao="Pix")

        self.assertEqual((pagamento.loja, pagamento.observacao), (self.loja, "Pix"))
        self.assertEqual(cliente.saldo_geral, Decimal('-30.00'))

    def test_pagamento_sem_observacao_recebe_texto_padrao(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")
        pagamento = registrar_pagamento(cliente, valor=Decimal('1.00'))
        self.assertEqual(pagamento.observacao, "Pagamento na caderneta")
