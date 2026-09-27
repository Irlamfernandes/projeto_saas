from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from application.vendas.exceptions import (
    EstoqueInsuficiente, ProdutoNaoEncontrado, SenhaIncorreta, VendaSemItens, VendaSemLoja,
)
from application.vendas.services import cancelar_venda, editar_venda, registrar_venda
from infrastructure.models import (
    Acao, Cliente, FormaDePagamento, ItemVenda, LojaModel, PagamentoCliente, Produto, RegistroDeAlteracao, Venda,
)


def saldo(cliente):
    return Cliente.objects.com_saldo().get(pk=cliente.pk).saldo_calculado


class ServicoDeVendaTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        self.bia = Cliente.objects.create(loja=self.loja, nome="Bia")
        self.arroz = Produto.objects.create(loja=self.loja, nome="Arroz", preco_venda=Decimal('20.00'), quantidade_estoque=10)
        self.feijao = Produto.objects.create(loja=self.loja, nome="Feijão", preco_venda=Decimal('8.00'), quantidade_estoque=3)
        self.usuario = get_user_model().objects.create_user(
            username="caixa", password="senha-certa", loja=self.loja, deve_trocar_senha=False,
        )

    def assertEstoque(self, produto, esperado):
        produto.refresh_from_db()
        self.assertEqual(produto.quantidade_estoque, esperado)

    def vender(self, itens, **extras):
        extras.setdefault('cliente', self.ana)
        return registrar_venda(itens=itens, usuario=self.usuario, **extras)


class RegistrarVendaTest(ServicoDeVendaTestCase):

    def test_venda_com_varios_produtos_baixa_o_estoque_de_cada_um(self):
        venda = self.vender([(self.arroz.pk, 2), (self.feijao.pk, 3)], forma_pagamento=FormaDePagamento.PIX, observacoes="obs")

        self.assertEqual(venda.valor_total, Decimal('64.00'))
        self.assertEqual(venda.observacoes, "obs")
        self.assertEqual(
            sorted((i.produto.nome, i.quantidade, i.preco_unitario) for i in venda.itens.all()),
            [("Arroz", 2, Decimal('20.00')), ("Feijão", 3, Decimal('8.00'))],
        )
        self.assertEstoque(self.arroz, 8)
        self.assertEstoque(self.feijao, 0)

    def test_mesmo_produto_repetido_vira_um_item_so(self):
        venda = self.vender([(self.arroz.pk, 1), (self.arroz.pk, 2)])
        self.assertEqual(venda.itens.get().quantidade, 3)

    def test_pago_no_ato_fica_ligado_a_venda_com_a_forma_de_pagamento(self):
        venda = self.vender([(self.arroz.pk, 3)], valor_pago=Decimal('15.00'), forma_pagamento=FormaDePagamento.PIX)

        pagamento = PagamentoCliente.objects.get()
        self.assertEqual((pagamento.venda, pagamento.cliente, pagamento.valor), (venda, self.ana, Decimal('15.00')))
        self.assertEqual(pagamento.forma_pagamento, FormaDePagamento.PIX)
        self.assertEqual(pagamento.observacao, f"Pagamento no ato da Venda #{venda.pk}")
        self.assertEqual(saldo(self.ana), Decimal('45.00'))

    def test_sem_valor_pago_nao_registra_pagamento(self):
        self.vender([(self.arroz.pk, 1)])
        self.assertFalse(PagamentoCliente.objects.exists())

    def test_venda_de_balcao_usa_a_loja_informada_e_nao_mexe_na_caderneta(self):
        venda = self.vender([(self.arroz.pk, 1)], cliente=None, loja=self.loja, forma_pagamento=FormaDePagamento.DINHEIRO,
                            valor_pago=Decimal('5.00'))

        self.assertIsNone(venda.cliente)
        self.assertEqual(venda.loja, self.loja)
        self.assertEqual(venda.forma_pagamento, FormaDePagamento.DINHEIRO)
        self.assertFalse(PagamentoCliente.objects.exists())

    def test_balcao_sem_loja_e_recusado(self):
        with self.assertRaises(VendaSemLoja):
            self.vender([(self.arroz.pk, 1)], cliente=None, loja=None)

    def test_sem_itens_e_recusado(self):
        with self.assertRaises(VendaSemItens):
            self.vender([])

    def test_estoque_insuficiente_nao_altera_nada(self):
        with self.assertRaisesMessage(EstoqueInsuficiente, "Estoque insuficiente para 'Feijão'. Disponível: 3."):
            self.vender([(self.arroz.pk, 1), (self.feijao.pk, 4)])

        self.assertFalse(Venda.objects.exists())
        self.assertEstoque(self.arroz, 10)

    def test_produto_de_outra_loja_nao_e_vendido(self):
        outra = LojaModel.objects.create(nome_loja="Loja B")
        de_fora = Produto.objects.create(loja=outra, nome="Café", preco_venda=Decimal('5'), quantidade_estoque=5)

        with self.assertRaises(ProdutoNaoEncontrado):
            self.vender([(de_fora.pk, 1)])
        self.assertEstoque(de_fora, 5)

    def test_registra_no_historico(self):
        venda = self.vender([(self.arroz.pk, 2)])

        registro = RegistroDeAlteracao.objects.get()
        self.assertEqual((registro.acao, registro.usuario, registro.loja), (Acao.VENDA_REGISTRADA, self.usuario, self.loja))
        self.assertEqual(registro.descricao, f"Venda #{venda.pk} · Ana · R$ 40,00")
        self.assertEqual(registro.detalhes['venda']['itens'], [{'produto': 'Arroz', 'quantidade': 2, 'preco_unitario': '20.00'}])


class EditarVendaTest(ServicoDeVendaTestCase):

    def setUp(self):
        super().setUp()
        self.venda = self.vender([(self.arroz.pk, 2)], valor_pago=Decimal('40.00'), forma_pagamento=FormaDePagamento.PIX)

    def editar(self, itens, **extras):
        extras.setdefault('cliente', self.ana)
        return editar_venda(self.venda, itens=itens, usuario=self.usuario, **extras)

    def test_troca_itens_devolve_o_estoque_antigo_e_baixa_o_novo(self):
        self.editar([(self.feijao.pk, 2)])

        self.assertEstoque(self.arroz, 10)
        self.assertEstoque(self.feijao, 1)
        self.assertEqual(self.venda.valor_total, Decimal('16.00'))

    def test_mesmo_produto_considera_o_estoque_devolvido(self):
        self.editar([(self.arroz.pk, 10)])
        self.assertEstoque(self.arroz, 0)

    def test_estoque_insuficiente_desfaz_tudo(self):
        with self.assertRaises(EstoqueInsuficiente):
            self.editar([(self.arroz.pk, 11)])

        self.assertEstoque(self.arroz, 8)
        self.assertEqual(self.venda.itens.get().quantidade, 2)

    def test_produto_que_ja_estava_mantem_o_preco_da_epoca(self):
        """Regressão: editar só a observação refazia o total com o preço de hoje."""
        Produto.objects.filter(pk=self.arroz.pk).update(preco_venda=Decimal('25.00'))

        self.editar([(self.arroz.pk, 2)], observacoes="só a observação")

        self.assertEqual(self.venda.valor_total, Decimal('40.00'))
        self.assertEqual(self.venda.itens.get().preco_unitario, Decimal('20.00'))

    def test_produto_novo_entra_com_o_preco_atual(self):
        Produto.objects.filter(pk=self.feijao.pk).update(preco_venda=Decimal('9.00'))
        self.editar([(self.arroz.pk, 2), (self.feijao.pk, 1)])
        self.assertEqual(self.venda.valor_total, Decimal('49.00'))

    def test_trocar_o_cliente_leva_junto_o_pagamento_feito_no_ato(self):
        """Regressão: o pagamento ficava com o cliente antigo (crédito falso) e o novo ficava devendo."""
        self.editar([(self.arroz.pk, 2)], cliente=self.bia, forma_pagamento=FormaDePagamento.DINHEIRO)

        self.assertEqual(saldo(self.ana), Decimal('0'))
        self.assertEqual(saldo(self.bia), Decimal('0'))
        pagamento = self.venda.pagamentos_no_ato.get()
        self.assertEqual((pagamento.cliente, pagamento.forma_pagamento), (self.bia, FormaDePagamento.DINHEIRO))

    def test_passar_para_balcao_tira_a_venda_e_o_pagamento_da_caderneta(self):
        self.editar([(self.arroz.pk, 2)], cliente=None)

        self.assertIsNone(self.venda.cliente)
        self.assertFalse(PagamentoCliente.objects.exists())
        self.assertEqual(saldo(self.ana), Decimal('0'))

    def test_registra_antes_e_depois_no_historico(self):
        self.editar([(self.feijao.pk, 1)], cliente=self.bia)

        registro = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_EDITADA)
        self.assertEqual(registro.detalhes['antes']['cliente'], "Ana")
        self.assertEqual(registro.detalhes['depois']['cliente'], "Bia")
        self.assertEqual(registro.descricao, f"Venda #{self.venda.pk} · Bia · R$ 40,00 → R$ 8,00")


class CancelarVendaTest(ServicoDeVendaTestCase):

    def setUp(self):
        super().setUp()
        self.venda = self.vender([(self.arroz.pk, 2), (self.feijao.pk, 1)], valor_pago=Decimal('10.00'))

    def test_devolve_o_estoque_e_apaga_a_venda_com_o_pagamento_no_ato(self):
        cancelar_venda(self.venda, usuario=self.usuario, senha="senha-certa", motivo="lançada em dobro")

        self.assertFalse(Venda.objects.exists())
        self.assertFalse(ItemVenda.objects.exists())
        self.assertFalse(PagamentoCliente.objects.exists())
        self.assertEstoque(self.arroz, 10)
        self.assertEstoque(self.feijao, 3)
        self.assertEqual(saldo(self.ana), Decimal('0'))

    def test_pagamento_avulso_da_caderneta_nao_e_afetado(self):
        PagamentoCliente.objects.create(loja=self.loja, cliente=self.ana, valor=Decimal('5.00'))
        cancelar_venda(self.venda, usuario=self.usuario, senha="senha-certa", motivo="erro")
        self.assertEqual(PagamentoCliente.objects.get().valor, Decimal('5.00'))

    def test_guarda_copia_da_venda_e_o_motivo_no_historico(self):
        numero = self.venda.pk
        cancelar_venda(self.venda, usuario=self.usuario, senha="senha-certa", motivo="cliente desistiu")

        registro = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_CANCELADA)
        self.assertEqual(registro.usuario, self.usuario)
        self.assertEqual(registro.detalhes['motivo'], "cliente desistiu")
        self.assertEqual(registro.detalhes['venda']['id'], numero)
        self.assertEqual(registro.detalhes['venda']['pago_no_ato'], ['10.00'])
        self.assertIn("motivo: cliente desistiu", registro.descricao)

    def test_senha_errada_nao_cancela_nada(self):
        with self.assertRaises(SenhaIncorreta):
            cancelar_venda(self.venda, usuario=self.usuario, senha="chute", motivo="erro")

        self.assertTrue(Venda.objects.filter(pk=self.venda.pk).exists())
        self.assertEstoque(self.arroz, 8)
        self.assertFalse(RegistroDeAlteracao.objects.filter(acao=Acao.VENDA_CANCELADA).exists())
