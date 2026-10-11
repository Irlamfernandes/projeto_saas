from decimal import Decimal
from django.test import TestCase
from infrastructure.models import ItemVenda, LojaModel, Produto, Unidade, Variacao, Venda
from interfaces.catalogo import catalogo_para_venda, itens_da_venda


class CatalogoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.pao = Produto.objects.create(
            loja=self.loja, nome="Pão", codigo_interno="P1", preco_venda=Decimal('10.00'), quantidade_estoque=3,
        )
        self.venda = Venda.objects.create(loja=self.loja)
        ItemVenda.objects.create(venda=self.venda, produto=self.pao, quantidade=2, preco_unitario=Decimal('9.00'))

    def catalogo(self, *produtos, venda=None):
        return catalogo_para_venda(Produto.objects.filter(pk__in=[p.pk for p in produtos]).order_by('nome'), venda)

    def test_catalogo_com_estoque_reservado_devolvido(self):
        self.assertEqual(self.catalogo(self.pao), [{
            'id': self.pao.pk, 'nome': "Pão", 'codigo': "P1", 'preco': '10.00', 'estoque': 3, 'unidade': 'un.', 'casas': 0,
            'variacoes': [],
        }])
        self.assertEqual(self.catalogo(self.pao, venda=self.venda)[0]['estoque'], 5)

    def test_linhas_repetidas_do_mesmo_produto_devolvem_tudo(self):
        ItemVenda.objects.create(venda=self.venda, produto=self.pao, quantidade=1, preco_unitario=Decimal('9.00'))
        self.assertEqual(self.catalogo(self.pao, venda=self.venda)[0]['estoque'], 6)

    def test_produto_por_quilo_e_sem_controle_de_estoque(self):
        queijo = Produto.objects.create(loja=self.loja, nome="Queijo", preco_venda=Decimal('39.90'), unidade=Unidade.QUILO,
                                        quantidade_estoque=Decimal('2.350'))
        bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('50'), controla_estoque=False)

        [sem_controle, por_quilo] = self.catalogo(queijo, bolo)

        self.assertEqual((por_quilo['estoque'], por_quilo['unidade'], por_quilo['casas']), (2.35, 'kg', 3))
        self.assertIsNone(sem_controle['estoque'])

    def test_variacoes_com_o_estoque_de_cada_uma_e_o_reservado_pela_venda(self):
        blusa = Produto.objects.create(loja=self.loja, nome="Blusa", preco_venda=Decimal('40'), quantidade_estoque=7)
        azul = Variacao.objects.create(produto=blusa, nome="Azul P", quantidade_estoque=4, acrescimo=Decimal('2.5'))
        branca = Variacao.objects.create(produto=blusa, nome="Branca P", quantidade_estoque=3)
        ItemVenda.objects.create(venda=self.venda, produto=blusa, variacao=azul, quantidade=2, preco_unitario=Decimal('42.50'),
                                 opcoes=[{'nome': 'Variação', 'valor': 'Azul P'}])

        [produto] = self.catalogo(blusa, venda=self.venda)

        self.assertEqual(produto['estoque'], 9)
        self.assertEqual(produto['variacoes'], [
            {'id': azul.pk, 'nome': "Azul P", 'acrescimo': '2.50', 'estoque': 6},
            {'id': branca.pk, 'nome': "Branca P", 'acrescimo': '0.00', 'estoque': 3},
        ])
        Produto.objects.filter(pk=blusa.pk).update(controla_estoque=False)
        self.assertIsNone(self.catalogo(blusa)[0]['variacoes'][0]['estoque'])

    def test_itens_da_venda_com_preco_e_variacao_da_epoca(self):
        self.assertEqual(itens_da_venda(self.venda), [
            {'id': self.pao.pk, 'quantidade': 2, 'preco': '9.00', 'variacao': None},
        ])
        blusa = Produto.objects.create(loja=self.loja, nome="Blusa", preco_venda=Decimal('40'))
        azul = Variacao.objects.create(produto=blusa, nome="Azul P")
        ItemVenda.objects.create(venda=self.venda, produto=blusa, variacao=azul, quantidade=1, preco_unitario=Decimal('40'),
                                 opcoes=[{'nome': 'Variação', 'valor': 'Azul P'}])
        self.assertEqual(itens_da_venda(self.venda)[1]['variacao'], azul.pk)
