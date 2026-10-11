from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from application.vendas.exceptions import (
    EstoqueInsuficiente, ProdutoNaoEncontrado, QuantidadeFracionada, SenhaIncorreta, VendaSemItens, VendaSemLoja,
)
from application.produtos.exceptions import VariacaoMudou, VariacaoNaoEscolhida
from application.vendas.services import cancelar_venda, editar_venda, registrar_venda
from infrastructure.models import (
    Acao, Cliente, FormaDePagamento, ItemVenda, LojaModel, PagamentoCliente, Parcela, Produto, RegistroDeAlteracao, Unidade,
    Variacao, Venda,
)


DIA_15 = date(2026, 10, 15)
DIA_30 = date(2026, 10, 30)


def vencimentos(venda):
    return list(venda.parcelas.values_list('vencimento', flat=True))


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
        with self.assertRaisesMessage(EstoqueInsuficiente, "Estoque insuficiente para 'Feijão'. Disponível: 3 un."):
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
        self.assertEqual(registro.detalhes['venda']['itens'], [
            {'produto': 'Arroz', 'quantidade': '2', 'unidade': 'un', 'preco_unitario': '20.00'},
        ])


class VencimentoTest(ServicoDeVendaTestCase):

    def test_venda_a_prazo_guarda_o_vencimento_e_vai_para_o_historico(self):
        venda = self.vender([(self.arroz.pk, 2)], valor_pago=Decimal('10.00'), forma_pagamento=FormaDePagamento.PIX,
                            vencimentos=[DIA_15])

        self.assertEqual(vencimentos(venda), [DIA_15])
        self.assertEqual(RegistroDeAlteracao.objects.get().detalhes['venda']['vencimentos'], ['2026-10-15'])

    def test_varios_vencimentos_ficam_em_ordem(self):
        venda = self.vender([(self.arroz.pk, 2)], vencimentos=[DIA_30, DIA_15])
        self.assertEqual(vencimentos(venda), [DIA_15, DIA_30])

    def test_sem_data_fica_sem_prazo(self):
        self.assertEqual(vencimentos(self.vender([(self.arroz.pk, 2)])), [])

    def test_balcao_e_venda_paga_no_ato_descartam_a_data(self):
        balcao = self.vender([(self.arroz.pk, 1)], cliente=None, loja=self.loja, vencimentos=[DIA_15])
        paga = self.vender([(self.arroz.pk, 1)], valor_pago=Decimal('20.00'), vencimentos=[DIA_15])

        self.assertFalse(Parcela.objects.filter(venda__in=[balcao, paga]).exists())

    def test_editar_troca_o_vencimento(self):
        venda = self.vender([(self.arroz.pk, 2)], vencimentos=[DIA_15])

        editar_venda(venda, itens=[(self.arroz.pk, 2)], cliente=self.ana, vencimentos=[DIA_30], usuario=self.usuario)

        self.assertEqual(vencimentos(venda), [DIA_30])
        registro = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_EDITADA)
        self.assertEqual((registro.detalhes['antes']['vencimentos'], registro.detalhes['depois']['vencimentos']),
                         (['2026-10-15'], ['2026-10-30']))

    def test_editar_sem_data_tira_o_prazo_e_passar_para_balcao_tambem(self):
        venda = self.vender([(self.arroz.pk, 2)], vencimentos=[DIA_15])
        editar_venda(venda, itens=[(self.arroz.pk, 2)], cliente=self.ana, usuario=self.usuario)
        self.assertEqual(vencimentos(venda), [])

        Parcela.objects.create(venda=venda, vencimento=DIA_15)
        editar_venda(venda, itens=[(self.arroz.pk, 2)], cliente=None, vencimentos=[DIA_30], usuario=self.usuario)
        self.assertEqual(vencimentos(venda), [])

    def test_cancelar_apaga_os_vencimentos(self):
        venda = self.vender([(self.arroz.pk, 2)], vencimentos=[DIA_15])
        cancelar_venda(venda, usuario=self.usuario, senha="senha-certa", motivo="erro")
        self.assertFalse(Parcela.objects.exists())


class UnidadesEControleDeEstoqueTest(ServicoDeVendaTestCase):

    def setUp(self):
        super().setUp()
        self.queijo = Produto.objects.create(loja=self.loja, nome="Queijo", preco_venda=Decimal('39.90'),
                                             unidade=Unidade.QUILO, quantidade_estoque=Decimal('2.500'))
        self.bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('50.00'), controla_estoque=False)

    def test_por_quilo_vende_fracao_e_o_total_fica_em_centavos(self):
        venda = self.vender([(self.queijo.pk, Decimal('0.350'))])

        self.assertEqual(venda.valor_total, Decimal('13.97'))
        self.assertEqual(venda.itens.get().quantidade, Decimal('0.350'))
        self.assertEstoque(self.queijo, Decimal('2.150'))
        self.assertEqual(RegistroDeAlteracao.objects.get().detalhes['venda']['itens'][0],
                         {'produto': 'Queijo', 'quantidade': '0.35', 'unidade': 'kg', 'preco_unitario': '39.90'})

    def test_fracao_onde_a_unidade_nao_aceita_e_recusada(self):
        casos = {
            (self.arroz.pk, Decimal('1.5')): "'Arroz' é vendido por unidade: use só números inteiros.",
            (self.queijo.pk, Decimal('0.3505')): "'Queijo' é vendido por quilo (kg): use no máximo 3 casas depois da vírgula.",
        }
        for item, mensagem in casos.items():
            with self.subTest(mensagem), self.assertRaisesMessage(QuantidadeFracionada, mensagem):
                self.vender([item])
        self.assertEstoque(self.arroz, 10)

    def test_estoque_insuficiente_mostra_a_unidade(self):
        with self.assertRaisesMessage(EstoqueInsuficiente, "Disponível: 2,5 kg"):
            self.vender([(self.queijo.pk, Decimal('3'))])

    def test_sem_controle_vende_qualquer_quantidade_sem_mexer_no_estoque(self):
        venda = self.vender([(self.bolo.pk, 40)])
        self.assertEqual(venda.valor_total, Decimal('2000.00'))
        self.assertEstoque(self.bolo, 0)

        cancelar_venda(venda, usuario=self.usuario, senha="senha-certa", motivo="teste")
        self.assertEstoque(self.bolo, 0)


class VariacoesNaVendaTest(ServicoDeVendaTestCase):
    """Blusa X (código 22) com 20 unidades: 10 Azul P, 5 Azul M e 5 Branca P. Cada venda baixa da variação vendida."""

    def setUp(self):
        super().setUp()
        self.blusa = Produto.objects.create(
            loja=self.loja, nome="Blusa X", codigo_interno="22", preco_venda=Decimal('40.00'),
            preco_custo=Decimal('15.00'), quantidade_estoque=20,
        )
        self.azul_p = Variacao.objects.create(produto=self.blusa, nome="Azul P", quantidade_estoque=10)
        self.azul_m = Variacao.objects.create(produto=self.blusa, nome="Azul M", quantidade_estoque=5)
        self.branca_p = Variacao.objects.create(
            produto=self.blusa, nome="Branca P", quantidade_estoque=5, acrescimo=Decimal('2.50'),
        )

    def assertEstoques(self, produto, variacoes):
        self.assertEstoque(self.blusa, produto)
        for variacao, esperado in zip((self.azul_p, self.azul_m, self.branca_p), variacoes, strict=True):
            variacao.refresh_from_db()
            self.assertEqual(variacao.quantidade_estoque, esperado, variacao.nome)

    def test_baixa_da_variacao_vendida_e_do_total_do_produto(self):
        venda = self.vender([(self.blusa.pk, 2, self.azul_p.pk)])

        item = venda.itens.get()
        self.assertEqual((item.variacao, item.preco_unitario, item.custo_unitario), (self.azul_p, Decimal('40.00'), Decimal('15.00')))
        self.assertEqual(item.opcoes, [{'nome': 'Variação', 'valor': 'Azul P'}])
        self.assertEqual(item.nome, "Blusa X (Azul P)")
        self.assertEstoques(18, [8, 5, 5])
        historico = RegistroDeAlteracao.objects.get(acao=Acao.VENDA_REGISTRADA)
        self.assertEqual(historico.detalhes['venda']['itens'][0]['produto'], "Blusa X (Azul P)")

    def test_acrescimo_da_variacao_entra_no_preco(self):
        venda = self.vender([(self.blusa.pk, 2, self.branca_p.pk)])
        self.assertEqual(venda.itens.get().preco_unitario, Decimal('42.50'))
        self.assertEqual(venda.valor_total, Decimal('85.00'))

    def test_mesma_variacao_se_junta_e_outra_vira_outro_item(self):
        venda = self.vender([
            (self.blusa.pk, 1, self.azul_p.pk), (self.blusa.pk, 1, self.azul_m.pk), (self.blusa.pk, 2, self.azul_p.pk),
        ])

        self.assertEqual(
            sorted((item.nome, item.quantidade) for item in venda.itens.all()),
            [("Blusa X (Azul M)", 1), ("Blusa X (Azul P)", 3)],
        )
        self.assertEstoques(16, [7, 4, 5])

    def test_o_estoque_conferido_e_o_da_variacao(self):
        with self.assertRaises(EstoqueInsuficiente) as erro:
            self.vender([(self.blusa.pk, 6, self.azul_m.pk)])  # o produto tem 20, mas a Azul M só 5
        self.assertEqual(str(erro.exception), "Estoque insuficiente para 'Blusa X (Azul M)'. Disponível: 5 un.")
        self.assertEstoques(20, [10, 5, 5])

    def test_produto_com_variacoes_exige_uma_delas(self):
        with self.assertRaises(VariacaoNaoEscolhida) as erro:
            self.vender([(self.blusa.pk, 1)])
        self.assertEqual(str(erro.exception), "Escolha a variação de 'Blusa X' (ex.: cor, tamanho).")

    def test_variacao_de_outro_produto_ou_excluida_e_recusada(self):
        outra = Variacao.objects.create(produto=self.arroz, nome="Integral")
        for produto, variacao in ((self.blusa, outra.pk), (self.blusa, 9999), (self.feijao, self.azul_p.pk)):
            with self.subTest(produto=produto.nome, variacao=variacao), self.assertRaises(VariacaoMudou) as erro:
                self.vender([(produto.pk, 1, variacao)])
        self.assertEqual(str(erro.exception), "As variações de 'Feijão' mudaram. Escolha o produto de novo.")
        self.assertEstoques(20, [10, 5, 5])

    def test_cancelar_devolve_para_a_variacao(self):
        venda = self.vender([(self.blusa.pk, 2, self.azul_m.pk)])
        cancelar_venda(venda, usuario=self.usuario, senha='senha-certa', motivo='desistiu')
        self.assertEstoques(20, [10, 5, 5])

    def test_editar_trocando_de_variacao_devolve_a_antiga_e_baixa_a_nova_com_o_preco_de_hoje(self):
        venda = self.vender([(self.blusa.pk, 2, self.azul_p.pk)])
        Produto.objects.filter(pk=self.blusa.pk).update(preco_venda=Decimal('50.00'))

        editar_venda(venda, itens=[(self.blusa.pk, 2, self.branca_p.pk)], cliente=self.ana, usuario=self.usuario)

        item = venda.itens.get()
        self.assertEqual((item.nome, item.preco_unitario), ("Blusa X (Branca P)", Decimal('52.50')))
        self.assertEstoques(18, [10, 5, 3])

    def test_editar_a_mesma_variacao_mantem_o_preco_da_epoca(self):
        venda = self.vender([(self.blusa.pk, 1, self.branca_p.pk)])
        Produto.objects.filter(pk=self.blusa.pk).update(preco_venda=Decimal('50.00'))
        Variacao.objects.filter(pk=self.branca_p.pk).update(nome="Branca PP", acrescimo=0)

        editar_venda(venda, itens=[(self.blusa.pk, 3, self.branca_p.pk)], cliente=self.ana, usuario=self.usuario)

        item = venda.itens.get()
        self.assertEqual((item.nome, item.preco_unitario), ("Blusa X (Branca P)", Decimal('42.50')))
        self.assertEstoques(17, [10, 5, 2])

    def test_sem_controle_de_estoque_nao_mexe_em_nenhuma_quantidade(self):
        Produto.objects.filter(pk=self.blusa.pk).update(controla_estoque=False)
        venda = self.vender([(self.blusa.pk, 50, self.azul_p.pk)])
        self.assertEqual(venda.itens.get().quantidade, 50)
        self.assertEstoques(20, [10, 5, 5])


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
