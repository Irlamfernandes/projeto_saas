from decimal import Decimal
from django.test import TestCase
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto, ProdutoImagem


class ProdutoModelTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja Teste", ativo=True)
        self.produto = Produto.objects.create(
            loja=self.loja,
            codigo_interno="P001",
            nome="Camiseta",
            categoria="Vestuário",
            descricao="Camiseta de algodão",
            preco_custo=Decimal('20.00'),
            preco_venda=Decimal('50.00'),
            margem_lucro=Decimal('150.00'),
            quantidade_estoque=10
        )

    # ---------------------------------------------------------
    # Testes do Model Produto
    # ---------------------------------------------------------
    def test_produto_str_com_codigo(self):
        """O método __str__ com código interno deve formatar corretamente."""
        self.assertEqual(str(self.produto), "[P001] Camiseta - R$ 50.00")

    def test_produto_str_sem_codigo(self):
        """O método __str__ sem código interno deve omiti-lo."""
        produto_sem_codigo = Produto.objects.create(
            loja=self.loja,
            nome="Calça",
            preco_venda=Decimal('100.00')
        )
        self.assertEqual(str(produto_sem_codigo), "Calça - R$ 100.00")

    def test_produto_defaults(self):
        """Verifica os valores padrão dos campos de preço, estoque e data."""
        produto_padrao = Produto.objects.create(
            loja=self.loja,
            nome="Produto Padrão",
            preco_venda=Decimal('10.00')
        )
        self.assertEqual(produto_padrao.preco_custo, Decimal('0.00'))
        self.assertEqual(produto_padrao.margem_lucro, Decimal('0.00'))
        self.assertEqual(produto_padrao.quantidade_estoque, 0)
        self.assertIsNotNone(produto_padrao.data_criacao)


class ProdutoImagemModelTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja Imagem", ativo=True)
        self.produto = Produto.objects.create(
            loja=self.loja,
            nome="Sapato",
            preco_venda=Decimal('120.00')
        )
        self.imagem = ProdutoImagem.objects.create(
            produto=self.produto,
            imagem_url="https://exemplo.com/imagem.jpg"
        )

    # ---------------------------------------------------------
    # Testes do Model ProdutoImagem
    # ---------------------------------------------------------
    def test_produto_imagem_str(self):
        """O método __str__ da imagem deve retornar o formato correto."""
        self.assertEqual(str(self.imagem), "Imagem de Sapato")

    def test_produto_imagem_creation(self):
        """Verifica os campos, data de criação e relacionamento da imagem do produto."""
        self.assertEqual(self.imagem.produto, self.produto)
        self.assertEqual(self.imagem.imagem_url, "https://exemplo.com/imagem.jpg")
        self.assertIsNotNone(self.imagem.data_criacao)
        self.assertIn(self.imagem, self.produto.imagens.all())
