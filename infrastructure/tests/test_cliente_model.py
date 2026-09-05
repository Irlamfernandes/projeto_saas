from decimal import Decimal
from django.test import TestCase
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.venda import Venda, PagamentoCliente


class ClienteModelTest(TestCase):

    def setUp(self):
        # Criação de lojas para testes de relacionamento
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        # Criação de um cliente vinculado à Loja 1
        self.cliente = Cliente.objects.create(
            loja=self.loja1,
            nome="João da Silva",
            telefone="24999999999",
            email="joao@email.com",
            endereco="Rua Teste, 123"
        )

    # ---------------------------------------------------------
    # Testes Básicos (Campos e __str__)
    # ---------------------------------------------------------
    def test_cliente_str(self):
        """O método __str__ deve retornar o nome do cliente."""
        self.assertEqual(str(self.cliente), "João da Silva")

    def test_cliente_creation(self):
        """Verifica se os campos do cliente são salvos corretamente."""
        self.assertEqual(self.cliente.nome, "João da Silva")
        self.assertEqual(self.cliente.telefone, "24999999999")
        self.assertEqual(self.cliente.email, "joao@email.com")
        self.assertEqual(self.cliente.endereco, "Rua Teste, 123")
        self.assertEqual(self.cliente.loja, self.loja1)
        self.assertIsNotNone(self.cliente.data_criacao)

    # ---------------------------------------------------------
    # Testes da Propriedade saldo_geral
    # ---------------------------------------------------------
    def test_saldo_geral_sem_movimentacoes(self):
        """O saldo geral deve ser Decimal('0.00') quando não houver compras ou pagamentos."""
        self.assertEqual(self.cliente.saldo_geral, Decimal('0.00'))

    def test_saldo_geral_com_compras_e_pagamentos(self):
        """O saldo geral deve calcular corretamente (total_compras - total_pagamentos)."""
        
        # Criação de vendas reais para o cliente na mesma loja
        Venda.objects.create(
            loja=self.loja1,
            cliente=self.cliente,
            valor_total=Decimal('150.50')
        )
        Venda.objects.create(
            loja=self.loja1,
            cliente=self.cliente,
            valor_total=Decimal('50.00')
        )  # Total de compras = 200.50

        # Criação de pagamentos reais para o cliente na mesma loja
        PagamentoCliente.objects.create(
            loja=self.loja1,
            cliente=self.cliente,
            valor=Decimal('70.00')
        )  # Total de pagamentos = 70.00

        # Saldo esperado: 200.50 - 70.00 = 130.50
        self.assertEqual(self.cliente.saldo_geral, Decimal('130.50'))