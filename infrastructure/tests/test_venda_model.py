from datetime import date
from decimal import Decimal
from django.core.exceptions import ValidationError
from django.test import TestCase
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto
from infrastructure.models.venda import ItemVenda, PagamentoCliente, Parcela, Venda


class VendaModelsTest(TestCase):

    def setUp(self):
        # Lojas para teste de isolamento/validação entre lojas
        self.loja1 = LojaModel.objects.create(nome_loja="Loja 1", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja 2", ativo=True)

        # Clientes
        self.cliente_loja1 = Cliente.objects.create(loja=self.loja1, nome="Cliente Loja 1")
        self.cliente_loja2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Loja 2")

        # Produtos
        self.produto_loja1 = Produto.objects.create(
            loja=self.loja1, nome="Produto 1", preco_venda=Decimal('10.00')
        )
        self.produto_loja2 = Produto.objects.create(
            loja=self.loja2, nome="Produto 2", preco_venda=Decimal('20.00')
        )

    # ---------------------------------------------------------
    # Testes do Model Venda
    # ---------------------------------------------------------
    def test_venda_str_nova_e_salva(self):
        """O método __str__ deve tratar venda nova e venda com ID corretamente."""
        venda_nova = Venda(loja=self.loja1, valor_total=Decimal('100.00'))
        self.assertEqual(str(venda_nova), "Venda #Nova - Cliente Não Identificado (R$ 100.00)")

        venda_salva = Venda.objects.create(
            loja=self.loja1, cliente=self.cliente_loja1, valor_total=Decimal('150.00')
        )
        self.assertEqual(str(venda_salva), f"Venda #{venda_salva.pk} - Cliente Loja 1 (R$ 150.00)")

    def test_venda_clean_cliente_outra_loja_raises_error(self):
        """Deve disparar ValidationError se o cliente pertencer a outra loja."""
        venda = Venda(loja=self.loja1, cliente=self.cliente_loja2, valor_total=Decimal('50.00'))
        with self.assertRaises(ValidationError) as ctx:
            venda.full_clean()
        self.assertIn('cliente', ctx.exception.error_dict)

    # ---------------------------------------------------------
    # Testes do Model ItemVenda
    # ---------------------------------------------------------
    def test_item_venda_subtotal_e_str(self):
        """Verifica o cálculo do subtotal e representação em string do item."""
        venda = Venda.objects.create(loja=self.loja1, valor_total=Decimal('30.00'))
        item = ItemVenda.objects.create(
            venda=venda,
            produto=self.produto_loja1,
            quantidade=3,
            preco_unitario=Decimal('10.00')
        )
        self.assertEqual(item.subtotal(), Decimal('30.00'))
        self.assertEqual(str(item), f"3x Produto 1 (Venda #{venda.pk})")

    def test_item_venda_clean_produto_outra_loja_raises_error(self):
        """Deve disparar ValidationError se o produto pertencer a outra loja."""
        venda = Venda.objects.create(loja=self.loja1, valor_total=Decimal('10.00'))
        item = ItemVenda(
            venda=venda,
            produto=self.produto_loja2,  # Produto da Loja 2
            quantidade=1,
            preco_unitario=Decimal('10.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            item.full_clean()
        self.assertIn('produto', ctx.exception.error_dict)

    # ---------------------------------------------------------
    # Testes do Model PagamentoCliente
    # ---------------------------------------------------------
    def test_pagamento_cliente_str(self):
        """O método __str__ do pagamento deve formatar corretamente."""
        pagamento = PagamentoCliente.objects.create(
            loja=self.loja1,
            cliente=self.cliente_loja1,
            valor=Decimal('75.50')
        )
        self.assertEqual(str(pagamento), "Pagamento - Cliente Loja 1 (R$ 75.50)")

    def test_pagamento_cliente_clean_outra_loja_raises_error(self):
        """Deve disparar ValidationError se o cliente do pagamento pertencer a outra loja."""
        pagamento = PagamentoCliente(
            loja=self.loja1,
            cliente=self.cliente_loja2,  # Cliente da Loja 2
            valor=Decimal('50.00')
        )
        with self.assertRaises(ValidationError) as ctx:
            pagamento.full_clean()
        self.assertIn('cliente', ctx.exception.error_dict)
    def test_parcela_str(self):
        venda = Venda.objects.create(loja=self.loja1, cliente=self.cliente_loja1, valor_total=Decimal('10.00'))
        parcela = Parcela.objects.create(venda=venda, vencimento=date(2026, 10, 15))
        self.assertEqual(str(parcela), f"Venda #{venda.pk} · vence 15/10/2026")
