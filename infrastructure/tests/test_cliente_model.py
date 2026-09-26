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

class SaldoAnotadoTest(TestCase):
    """O saldo calculado em lote (com_saldo) deve bater com o saldo individual e evitar N+1."""

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.devendo = Cliente.objects.create(loja=self.loja, nome="Devendo")
        self.credito = Cliente.objects.create(loja=self.loja, nome="Crédito")
        self.zerado = Cliente.objects.create(loja=self.loja, nome="Zerado")
        Venda.objects.create(loja=self.loja, cliente=self.devendo, valor_total=Decimal('100.00'))
        Venda.objects.create(loja=self.loja, cliente=self.devendo, valor_total=Decimal('50.50'))
        PagamentoCliente.objects.create(loja=self.loja, cliente=self.devendo, valor=Decimal('30.00'))
        PagamentoCliente.objects.create(loja=self.loja, cliente=self.credito, valor=Decimal('20.00'))

    def test_valores(self):
        saldos = dict(Cliente.objects.com_saldo().values_list('nome', 'saldo_calculado'))
        self.assertEqual(saldos, {
            "Devendo": Decimal('120.50'), "Crédito": Decimal('-20.00'), "Zerado": Decimal('0.00'),
        })

    def test_saldo_geral_usa_o_valor_anotado_sem_novas_consultas(self):
        clientes = list(Cliente.objects.com_saldo())
        with self.assertNumQueries(0):
            self.assertEqual([c.saldo_geral for c in clientes], [Decimal('120.50'), Decimal('-20.00'), Decimal('0.00')])

    def test_permite_filtrar_e_ordenar_pelo_saldo(self):
        devedores = Cliente.objects.com_saldo().filter(saldo_calculado__gt=0)
        self.assertEqual(list(devedores), [self.devendo])
