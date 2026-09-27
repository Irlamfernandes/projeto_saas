from decimal import Decimal
from django.test import TestCase
from infrastructure.models import LojaModel, Produto, Venda, ItemVenda
from interfaces.catalogo import catalogo_para_venda, itens_da_venda


class CatalogoTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.pao = Produto.objects.create(loja=loja, nome="Pão", codigo_interno="P1", preco_venda=Decimal('10.00'), quantidade_estoque=3)
        self.venda = Venda.objects.create(loja=loja)
        ItemVenda.objects.create(venda=self.venda, produto=self.pao, quantidade=2, preco_unitario=Decimal('9.00'))

    def test_catalogo_com_estoque_reservado_devolvido(self):
        self.assertEqual(catalogo_para_venda([self.pao]), [{'id': self.pao.pk, 'nome': "Pão", 'codigo': "P1", 'preco': '10.00', 'estoque': 3}])
        self.assertEqual(catalogo_para_venda([self.pao], {self.pao.pk: 2})[0]['estoque'], 5)

    def test_itens_da_venda_com_preco_da_epoca(self):
        self.assertEqual(itens_da_venda(self.venda), [{'id': self.pao.pk, 'quantidade': 2, 'preco': '9.00'}])
