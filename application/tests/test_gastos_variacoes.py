from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from application.gastos.exceptions import EstoqueJaUsado, EstoqueNaoCobreAPerda
from application.gastos.services import excluir_compra, excluir_perda, registrar_compra, registrar_perda
from application.produtos.exceptions import VariacaoNaoEscolhida
from application.vendas.services import registrar_venda
from infrastructure.models import Acao, LojaModel, Produto, RegistroDeAlteracao, Variacao

DIA = date(2026, 10, 1)


class CompraEPerdaComVariacoesTest(TestCase):
    """Blusa X com 10 Azul P e 5 Branca P: compra soma e perda tira da variação escolhida (e do total)."""

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.usuario = get_user_model().objects.create_user(username="u", password="x", loja=self.loja,
                                                            deve_trocar_senha=False)
        self.blusa = Produto.objects.create(loja=self.loja, nome="Blusa X", preco_venda=Decimal('40'),
                                            preco_custo=Decimal('15'), quantidade_estoque=15)
        self.azul = Variacao.objects.create(produto=self.blusa, nome="Azul P", quantidade_estoque=10)
        self.branca = Variacao.objects.create(produto=self.blusa, nome="Branca P", quantidade_estoque=5)

    def assertEstoques(self, produto, azul, branca):
        for registro, esperado in ((self.blusa, produto), (self.azul, azul), (self.branca, branca)):
            registro.refresh_from_db()
            self.assertEqual(registro.quantidade_estoque, esperado, str(registro))

    def comprar(self, *itens):
        return registrar_compra(loja=self.loja, itens=list(itens), data=DIA, usuario=self.usuario)

    def test_compra_soma_na_variacao_e_excluir_tira_de_novo(self):
        compra = self.comprar((self.blusa.pk, Decimal('4'), Decimal('16'), self.branca.pk))

        item = compra.itens.get()
        self.assertEqual((item.variacao, item.variacao_nome, item.nome), (self.branca, "Branca P", "Blusa X (Branca P)"))
        self.assertEstoques(19, 10, 9)
        historico = RegistroDeAlteracao.objects.get(acao=Acao.COMPRA_REGISTRADA)
        self.assertEqual(historico.detalhes['itens'], ["4× Blusa X (Branca P) a R$ 16,00"])

        excluir_compra(compra, usuario=self.usuario)
        self.assertEstoques(15, 10, 5)

    def test_compra_de_produto_com_variacoes_exige_a_variacao(self):
        with self.assertRaises(VariacaoNaoEscolhida):
            self.comprar((self.blusa.pk, Decimal('1'), Decimal('16')))
        self.assertEstoques(15, 10, 5)

    def test_nao_exclui_a_compra_se_a_variacao_ja_vendeu(self):
        compra = self.comprar((self.blusa.pk, Decimal('2'), Decimal('16'), self.branca.pk))
        registrar_venda(itens=[(self.blusa.pk, 6, self.branca.pk)], loja=self.loja, usuario=self.usuario)

        with self.assertRaises(EstoqueJaUsado) as erro:
            excluir_compra(compra, usuario=self.usuario)
        self.assertIn("'Blusa X (Branca P)'", str(erro.exception))
        self.assertEstoques(11, 10, 1)

    def test_perda_tira_da_variacao_e_excluir_devolve(self):
        perda = registrar_perda(loja=self.loja, produto_id=self.blusa.pk, variacao_id=self.azul.pk, quantidade=Decimal('3'),
                                data=DIA, motivo="Rasgou", usuario=self.usuario)

        self.assertEqual((perda.variacao, perda.variacao_nome, str(perda)), (self.azul, "Azul P", "Perda de Blusa X (Azul P) · 01/10/2026"))
        self.assertEstoques(12, 7, 5)
        historico = RegistroDeAlteracao.objects.get(acao=Acao.PERDA_REGISTRADA)
        self.assertTrue(historico.descricao.startswith("3× Blusa X (Azul P) · Rasgou"))

        excluir_perda(perda, usuario=self.usuario)
        self.assertEstoques(15, 10, 5)

    def test_perda_maior_que_a_variacao_tem_e_recusada(self):
        with self.assertRaises(EstoqueNaoCobreAPerda) as erro:
            registrar_perda(loja=self.loja, produto_id=self.blusa.pk, variacao_id=self.branca.pk, quantidade=Decimal('6'),
                            data=DIA, motivo="x", usuario=self.usuario)  # o produto tem 15, mas a Branca P só 5
        self.assertEqual(str(erro.exception), "'Blusa X (Branca P)' tem só 5 un. em estoque.")

    def test_sem_controle_de_estoque_nao_mexe_nas_quantidades(self):
        Produto.objects.filter(pk=self.blusa.pk).update(controla_estoque=False)
        self.comprar((self.blusa.pk, Decimal('4'), Decimal('16'), self.azul.pk))
        registrar_perda(loja=self.loja, produto_id=self.blusa.pk, variacao_id=self.azul.pk, quantidade=Decimal('30'),
                        data=DIA, motivo="x", usuario=self.usuario)
        self.assertEstoques(15, 10, 5)
        self.assertEqual(str(self.azul), "Blusa X (Azul P)")
