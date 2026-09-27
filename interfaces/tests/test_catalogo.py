from decimal import Decimal
from django.test import TestCase
from infrastructure.models import LojaModel, Produto, Unidade, Venda, ItemVenda
from interfaces.catalogo import catalogo_para_venda, itens_da_venda


class CatalogoTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.pao = Produto.objects.create(loja=loja, nome="Pão", codigo_interno="P1", preco_venda=Decimal('10.00'), quantidade_estoque=3)
        self.venda = Venda.objects.create(loja=loja)
        ItemVenda.objects.create(venda=self.venda, produto=self.pao, quantidade=2, preco_unitario=Decimal('9.00'))

    def test_catalogo_com_estoque_reservado_devolvido(self):
        self.assertEqual(catalogo_para_venda([self.pao]), [{
            'id': self.pao.pk, 'nome': "Pão", 'codigo': "P1", 'preco': '10.00', 'estoque': 3, 'unidade': 'un.', 'casas': 0,
            'opcoes': [],
        }])
        self.assertEqual(catalogo_para_venda([self.pao], {self.pao.pk: 2})[0]['estoque'], 5)

    def test_produto_por_quilo_e_sem_controle_de_estoque(self):
        queijo = Produto(nome="Queijo", preco_venda=Decimal('39.90'), unidade=Unidade.QUILO, quantidade_estoque=Decimal('2.350'))
        bolo = Produto(nome="Bolo", preco_venda=Decimal('50'), controla_estoque=False, quantidade_estoque=Decimal('0'))

        [por_quilo, sem_controle] = catalogo_para_venda([queijo, bolo])

        self.assertEqual((por_quilo['estoque'], por_quilo['unidade'], por_quilo['casas']), (2.35, 'kg', 3))
        self.assertIsNone(sem_controle['estoque'])

    def test_itens_da_venda_com_preco_da_epoca(self):
        self.assertEqual(itens_da_venda(self.venda), [{'id': self.pao.pk, 'quantidade': 2, 'preco': '9.00', 'opcoes': {}}])

    def test_opcoes_do_produto_e_escolhas_do_item(self):
        opcoes = [{'nome': 'Tamanho', 'valores': [{'nome': 'G', 'acrescimo': '5.00'}]}]
        self.pao.opcoes = opcoes
        ItemVenda.objects.filter(venda=self.venda).update(opcoes=[{'nome': 'Tamanho', 'valor': 'G'}])

        self.assertEqual(catalogo_para_venda([self.pao])[0]['opcoes'], opcoes)
        self.assertEqual(itens_da_venda(self.venda)[0]['opcoes'], {'Tamanho': 'G'})
