from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from application.vendas.selectors import produtos_da_loja, produtos_em_estoque_do_usuario, vendas_do_usuario
from infrastructure.models import LojaModel, Produto, Venda


def _criar_produto(loja, nome, codigo='', estoque=10):
    return Produto.objects.create(
        loja=loja, nome=nome, codigo_interno=codigo,
        preco_venda=Decimal('10.00'), quantidade_estoque=estoque,
    )


class ConsultasPorUsuarioTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        self.usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        self.superusuario = SimpleNamespace(is_superuser=True, loja=None)

    def test_vendas_do_usuario_filtra_pela_loja_e_ordena_mais_recentes_primeiro(self):
        antiga = Venda.objects.create(loja=self.loja)
        recente = Venda.objects.create(loja=self.loja)
        Venda.objects.create(loja=self.outra_loja)

        self.assertEqual(list(vendas_do_usuario(self.usuario)), [recente, antiga])
        self.assertEqual(vendas_do_usuario(self.superusuario).count(), 3)

    def test_produtos_em_estoque_exclui_zerados_e_outras_lojas(self):
        com_estoque = _criar_produto(self.loja, "Arroz")
        _criar_produto(self.loja, "Feijão", estoque=0)
        _criar_produto(self.outra_loja, "Milho")

        self.assertEqual(list(produtos_em_estoque_do_usuario(self.usuario)), [com_estoque])
        self.assertEqual(produtos_em_estoque_do_usuario(self.superusuario).count(), 2)

    def test_produtos_da_loja_nao_inclui_outra_loja(self):
        daqui = _criar_produto(self.loja, "Pão")
        _criar_produto(self.outra_loja, "Guaraná")
        self.assertEqual(list(produtos_da_loja(self.loja)), [daqui])
