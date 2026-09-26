from decimal import Decimal
from django.test import TestCase
from application.vendas.exceptions import EstoqueInsuficiente, ProdutoNaoEncontrado
from application.vendas.services import editar_venda, registrar_venda
from infrastructure.models import Cliente, ItemVenda, LojaModel, PagamentoCliente, Produto, Venda


class ServicoDeVendaTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.cliente = Cliente.objects.create(loja=self.loja, nome="Cliente A")
        self.arroz = Produto.objects.create(
            loja=self.loja, nome="Arroz", codigo_interno="AR01",
            preco_venda=Decimal('20.00'), quantidade_estoque=10,
        )
        self.feijao = Produto.objects.create(
            loja=self.loja, nome="Feijão", codigo_interno="FE01",
            preco_venda=Decimal('8.00'), quantidade_estoque=3,
        )

    def assertEstoque(self, produto, esperado):
        produto.refresh_from_db()
        self.assertEqual(produto.quantidade_estoque, esperado)


class RegistrarVendaTest(ServicoDeVendaTestCase):

    def test_cria_venda_item_baixa_estoque_e_registra_pagamento(self):
        venda = registrar_venda(
            cliente=self.cliente, termo_produto="AR01", quantidade=3,
            valor_pago=Decimal('15.00'), observacoes="obs",
        )

        self.assertEqual(venda.loja, self.loja)
        self.assertEqual(venda.valor_total, Decimal('60.00'))
        self.assertEqual(venda.observacoes, "obs")
        item = venda.itens.get()
        self.assertEqual((item.produto, item.quantidade, item.preco_unitario), (self.arroz, 3, Decimal('20.00')))
        self.assertEstoque(self.arroz, 7)
        pagamento = PagamentoCliente.objects.get()
        self.assertEqual((pagamento.cliente, pagamento.valor), (self.cliente, Decimal('15.00')))
        self.assertIn(f"#{venda.pk}", pagamento.observacao)

    def test_sem_valor_pago_nao_registra_pagamento(self):
        registrar_venda(cliente=self.cliente, termo_produto="AR01", quantidade=1)
        self.assertFalse(PagamentoCliente.objects.exists())

    def test_estoque_insuficiente_nao_altera_nada(self):
        with self.assertRaisesMessage(EstoqueInsuficiente, "Disponível: 3"):
            registrar_venda(cliente=self.cliente, termo_produto="FE01", quantidade=4, valor_pago=Decimal('5'))

        self.assertFalse(Venda.objects.exists())
        self.assertFalse(PagamentoCliente.objects.exists())
        self.assertEstoque(self.feijao, 3)

    def test_produto_nao_encontrado(self):
        with self.assertRaisesMessage(ProdutoNaoEncontrado, "'Macarrão'"):
            registrar_venda(cliente=self.cliente, termo_produto="Macarrão", quantidade=1)

    def test_nao_vende_produto_de_loja_diferente_da_do_cliente(self):
        outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        cliente_outra_loja = Cliente.objects.create(loja=outra_loja, nome="Cliente B")

        with self.assertRaises(ProdutoNaoEncontrado):
            registrar_venda(cliente=cliente_outra_loja, termo_produto="AR01", quantidade=1)


class EditarVendaTest(ServicoDeVendaTestCase):

    def setUp(self):
        super().setUp()
        self.venda = registrar_venda(cliente=self.cliente, termo_produto="AR01", quantidade=2)

    def test_troca_produto_devolve_estoque_antigo_e_baixa_o_novo(self):
        editar_venda(self.venda, cliente=self.cliente, termo_produto="FE01", quantidade=3, observacoes="trocado")

        self.assertEstoque(self.arroz, 10)
        self.assertEstoque(self.feijao, 0)
        self.venda.refresh_from_db()
        self.assertEqual(self.venda.valor_total, Decimal('24.00'))
        self.assertEqual(self.venda.observacoes, "trocado")
        self.assertEqual(ItemVenda.objects.get(venda=self.venda).produto, self.feijao)

    def test_mesmo_produto_considera_o_estoque_devolvido(self):
        Produto.objects.filter(pk=self.arroz.pk).update(quantidade_estoque=0)

        editar_venda(self.venda, cliente=self.cliente, termo_produto="AR01", quantidade=2)

        self.assertEstoque(self.arroz, 0)

    def test_estoque_insuficiente_desfaz_a_devolucao(self):
        with self.assertRaises(EstoqueInsuficiente):
            editar_venda(self.venda, cliente=self.cliente, termo_produto="FE01", quantidade=4)

        self.assertEstoque(self.arroz, 8)
        self.assertEstoque(self.feijao, 3)
        self.assertEqual(ItemVenda.objects.get(venda=self.venda).produto, self.arroz)

    def test_venda_sem_item_recebe_item_novo(self):
        self.venda.itens.all().delete()

        editar_venda(self.venda, cliente=self.cliente, termo_produto="AR01", quantidade=1)

        self.assertEqual(self.venda.itens.get().quantidade, 1)
        self.assertEstoque(self.arroz, 7)

    def test_permite_remover_o_cliente(self):
        editar_venda(self.venda, cliente=None, termo_produto="AR01", quantidade=2)

        self.venda.refresh_from_db()
        self.assertIsNone(self.venda.cliente)
