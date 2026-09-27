from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from application.produtos.selectors import categorias_em_uso, filtrar_produtos, fotos_disponiveis, produtos_do_usuario
from infrastructure.models import LojaModel, Produto
from infrastructure.models.produto import ProdutoImagem


class ProdutosSelectorsTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        self.camiseta = self._produto("Camiseta", "CAM01", "Roupas", estoque=2, preco='50')
        self.bone = self._produto("Boné", "BON01", "Acessórios", estoque=10, preco='30')
        self.caneca = self._produto("Caneca", "", "", estoque=5, preco='20')
        self._produto("Calça", "CAL01", "Roupas", estoque=1, preco='90', loja=outra_loja)
        self.produtos = produtos_do_usuario(SimpleNamespace(is_superuser=False, loja=self.loja))

    def _produto(self, nome, codigo, categoria, estoque, preco, loja=None):
        return Produto.objects.create(
            loja=loja or self.loja, nome=nome, codigo_interno=codigo, categoria=categoria,
            quantidade_estoque=estoque, preco_venda=Decimal(preco),
        )

    def test_produtos_do_usuario_filtra_pela_loja(self):
        self.assertEqual(self.produtos.count(), 3)
        self.assertEqual(produtos_do_usuario(SimpleNamespace(is_superuser=True, loja=None)).count(), 4)

    def test_sem_criterios_ordena_mais_recentes_primeiro(self):
        self.assertEqual(list(filtrar_produtos(self.produtos)), [self.caneca, self.bone, self.camiseta])

    def test_busca_por_nome_ou_codigo(self):
        self.assertEqual(list(filtrar_produtos(self.produtos, busca="cam")), [self.camiseta])
        self.assertEqual(list(filtrar_produtos(self.produtos, busca="bon01")), [self.bone])

    def test_filtra_categoria_exata(self):
        self.assertEqual(list(filtrar_produtos(self.produtos, categoria="Roupas")), [self.camiseta])

    def test_estoque_baixo_inclui_o_limite(self):
        resultado = filtrar_produtos(self.produtos, baixo_estoque=True, ordem='nome')
        self.assertEqual(list(resultado), [self.camiseta, self.caneca])

    def test_ordenacao(self):
        self.assertEqual(list(filtrar_produtos(self.produtos, ordem='-preco_venda')), [self.camiseta, self.bone, self.caneca])

    def test_categorias_em_uso_sem_vazias_nem_repetidas(self):
        self._produto("Meia", "MEI01", "Roupas", estoque=1, preco='5')
        self.assertEqual(categorias_em_uso(self.produtos), ["Acessórios", "Roupas"])


class FotosDisponiveisTest(TestCase):

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        self.produto = Produto.objects.create(loja=loja, nome="Bolo", preco_venda=Decimal('30'))

    def _fotos(self, quantidade):
        for _ in range(quantidade):
            ProdutoImagem.objects.create(produto=self.produto, imagem_url="https://x.co/f.webp")

    def test_desconta_as_fotos_que_o_produto_ja_tem(self):
        self._fotos(2)
        self.assertEqual(fotos_disponiveis(self.produto), 3)

    def test_nunca_fica_negativo(self):
        self._fotos(7)  # cadastradas antes do limite existir
        self.assertEqual(fotos_disponiveis(self.produto), 0)
