from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from application.gastos.exceptions import (
    CompraSemItens, EstoqueJaUsado, EstoqueNaoCobreAPerda, ProdutoDeOutraLoja, QuantidadeInvalidaParaUnidade,
)
from application.gastos.services import (
    excluir_compra, excluir_despesa, excluir_perda, registrar_compra, registrar_despesa, registrar_perda,
)
from application.vendas.services import editar_venda, registrar_venda
from infrastructure.models import Acao, Compra, Despesa, LojaModel, Perda, Produto, RegistroDeAlteracao, Unidade

DIA = date(2026, 9, 10)


class GastosTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.usuario = get_user_model().objects.create_user(username="u", password="x", loja=self.loja, deve_trocar_senha=False)
        self.bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('30'), preco_custo=Decimal('10'),
                                           quantidade_estoque=5)
        self.queijo = Produto.objects.create(loja=self.loja, nome="Queijo", preco_venda=Decimal('40'), unidade=Unidade.QUILO,
                                             quantidade_estoque=Decimal('1'))
        self.servico = Produto.objects.create(loja=self.loja, nome="Frete", preco_venda=Decimal('15'), controla_estoque=False)

    def estoque(self, produto):
        produto.refresh_from_db()
        return produto.quantidade_estoque

    def comprar(self, itens, **extras):
        return registrar_compra(loja=self.loja, itens=itens, data=DIA, usuario=self.usuario, **extras)

    def registro(self, acao):
        return RegistroDeAlteracao.objects.get(acao=acao)


class CompraTest(GastosTestCase):

    def test_soma_no_estoque_atualiza_o_custo_e_registra(self):
        compra = self.comprar([(self.bolo.pk, Decimal('3'), Decimal('12.00')),
                               (self.queijo.pk, Decimal('2.5'), Decimal('39.90'))], fornecedor="Atacadão")

        self.assertEqual(compra.valor_total, Decimal('135.75'))
        self.assertEqual((self.estoque(self.bolo), self.estoque(self.queijo)), (Decimal('8'), Decimal('3.5')))
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.preco_custo, Decimal('12.00'))
        registro = self.registro(Acao.COMPRA_REGISTRADA)
        self.assertEqual(registro.descricao, f"Compra #{compra.pk} · Atacadão · R$ 135,75")
        self.assertEqual(registro.detalhes['itens'], ["3× Bolo a R$ 12,00", "2,5 kg Queijo a R$ 39,90"])

    def test_sem_atualizar_o_custo_e_produto_sem_controle(self):
        self.comprar([(self.bolo.pk, Decimal('1'), Decimal('99')), (self.servico.pk, Decimal('4'), Decimal('5'))],
                     atualizar_custo=False)
        self.bolo.refresh_from_db()
        self.assertEqual(self.bolo.preco_custo, Decimal('10.00'))
        self.assertEqual(self.estoque(self.servico), Decimal('0'))

    def test_recusas(self):
        outra = Produto.objects.create(loja=LojaModel.objects.create(nome_loja="Outra"), nome="X", preco_venda=Decimal('1'))
        casos = {
            'sem itens': ([], CompraSemItens),
            'de outra loja': ([(outra.pk, Decimal('1'), Decimal('1'))], ProdutoDeOutraLoja),
            'fração em unidade': ([(self.bolo.pk, Decimal('1.5'), Decimal('1'))], QuantidadeInvalidaParaUnidade),
        }
        for nome, (itens, erro) in casos.items():
            with self.subTest(nome), self.assertRaises(erro):
                self.comprar(itens)
        self.assertFalse(Compra.objects.exists())
        self.assertEqual(self.estoque(self.bolo), Decimal('5'))

    def test_excluir_tira_do_estoque_e_registra(self):
        compra = self.comprar([(self.bolo.pk, Decimal('3'), Decimal('12')), (self.bolo.pk, Decimal('2'), Decimal('12')),
                               (self.servico.pk, Decimal('1'), Decimal('5'))])

        excluir_compra(compra, usuario=self.usuario)

        self.assertFalse(Compra.objects.exists())
        self.assertEqual(self.estoque(self.bolo), Decimal('5'))
        self.assertIn("Bolo", str(self.registro(Acao.COMPRA_EXCLUIDA).detalhes['itens']))

    def test_nao_exclui_se_o_estoque_da_compra_ja_foi_usado(self):
        compra = self.comprar([(self.bolo.pk, Decimal('3'), Decimal('12'))])
        Produto.objects.filter(pk=self.bolo.pk).update(quantidade_estoque=2)

        with self.assertRaisesMessage(EstoqueJaUsado, "'Bolo' desta compra já foi vendida"):
            excluir_compra(compra, usuario=self.usuario)
        self.assertTrue(Compra.objects.exists())


class DespesaTest(GastosTestCase):

    def test_registra_e_exclui_com_historico(self):
        despesa = registrar_despesa(loja=self.loja, data=DIA, categoria="Luz", descricao="agosto", valor=Decimal('150.40'),
                                    usuario=self.usuario)
        self.assertEqual(self.registro(Acao.DESPESA_REGISTRADA).descricao, "Luz · agosto · R$ 150,40")

        excluir_despesa(despesa, usuario=self.usuario)

        self.assertFalse(Despesa.objects.exists())
        self.assertEqual(self.registro(Acao.DESPESA_EXCLUIDA).detalhes, {'data': '2026-09-10', 'descricao': 'agosto'})


class PerdaTest(GastosTestCase):

    def perder(self, produto, quantidade, motivo="Venceu"):
        return registrar_perda(loja=self.loja, produto_id=produto.pk, quantidade=Decimal(quantidade), data=DIA,
                               motivo=motivo, usuario=self.usuario)

    def test_baixa_o_estoque_pelo_custo_de_hoje(self):
        perda = self.perder(self.bolo, '2')

        self.assertEqual((perda.custo_unitario, perda.valor), (Decimal('10.00'), Decimal('20.00')))
        self.assertEqual(self.estoque(self.bolo), Decimal('3'))
        self.assertEqual(self.registro(Acao.PERDA_REGISTRADA).descricao, "2× Bolo · Venceu · R$ 20,00")
        self.assertEqual(str(perda), f"Perda de Bolo · {DIA:%d/%m/%Y}")

    def test_nao_perde_mais_do_que_tem_nem_fracao_indevida(self):
        with self.assertRaisesMessage(EstoqueNaoCobreAPerda, "'Queijo' tem só 1 kg em estoque."):
            self.perder(self.queijo, '1.5')
        with self.assertRaises(QuantidadeInvalidaParaUnidade):
            self.perder(self.bolo, '0.5')
        self.assertFalse(Perda.objects.exists())

    def test_sem_controle_registra_sem_mexer_no_estoque(self):
        self.perder(self.servico, '3', motivo="Consumo próprio")
        self.assertEqual(self.estoque(self.servico), Decimal('0'))

    def test_excluir_devolve_ao_estoque(self):
        perda = self.perder(self.queijo, '0.25')
        excluir_perda(perda, usuario=self.usuario)
        self.assertEqual(self.estoque(self.queijo), Decimal('1'))
        self.assertFalse(Perda.objects.exists())
        self.assertTrue(RegistroDeAlteracao.objects.filter(acao=Acao.PERDA_EXCLUIDA).exists())


class CustoNaVendaTest(GastosTestCase):

    def test_venda_guarda_o_custo_do_dia_e_a_edicao_mantem_o_da_epoca(self):
        venda = registrar_venda(itens=[(self.bolo.pk, 1)], loja=self.loja, forma_pagamento='pix')
        self.assertEqual(venda.itens.get().custo_unitario, Decimal('10.00'))

        Produto.objects.filter(pk=self.bolo.pk).update(preco_custo=Decimal('14'))
        editar_venda(venda, itens=[(self.bolo.pk, 2), (self.queijo.pk, Decimal('0.5'))], forma_pagamento='pix')

        custos = {item.produto.nome: item.custo_unitario for item in venda.itens.all()}
        self.assertEqual(custos, {'Bolo': Decimal('10.00'), 'Queijo': Decimal('0.00')})
