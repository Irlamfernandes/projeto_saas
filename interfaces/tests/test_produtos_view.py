from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto, ProdutoImagem

User = get_user_model()


class ProdutosViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(
            username="admin", password="password"
        )
        self.user_loja1 = User.objects.create_user(
            username="user_loja1", password="password", loja=self.loja1
        )
        
        # Cria usuário sem loja ignorando o full_clean para testar permissão
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                username="user_sem_loja", password="password", loja=None
            )

        self.produto_l1 = Produto.objects.create(
            loja=self.loja1, 
            codigo_interno="COD01",
            nome="Camiseta Polo", 
            categoria="Vestuário",
            preco_venda=Decimal('50.00'),
            quantidade_estoque=2  # Baixo estoque
        )
        self.produto_l2 = Produto.objects.create(
            loja=self.loja2, 
            codigo_interno="COD02",
            nome="Calça Jeans", 
            categoria="Vestuário",
            preco_venda=Decimal('100.00'),
            quantidade_estoque=20
        )

        self.url_produtos = reverse('produtos')

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar a listagem de produtos."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self.url_produtos)
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_ve_apenas_produtos_da_sua_loja(self):
        """Usuário comum visualiza somente os produtos pertencentes à sua loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_produtos)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camiseta Polo")
        self.assertNotContains(response, "Calça Jeans")

    def test_superuser_ve_todos_os_produtos(self):
        """Superusuário visualiza produtos de todas as lojas."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_produtos)
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camiseta Polo")
        self.assertContains(response, "Calça Jeans")

    def test_filtro_busca_por_nome_ou_codigo(self):
        """Filtra produtos corretamente usando o parâmetro de busca 'q'."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_produtos, {'q': 'COD01'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camiseta Polo")
        self.assertNotContains(response, "Calça Jeans")

    def test_busca_muito_longa_redireciona_com_erro(self):
        """Busca com mais de 100 caracteres exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_produtos, {'q': 'a' * 101})
        self.assertRedirects(response, self.url_produtos)

    def test_filtro_baixo_estoque(self):
        """Filtra apenas produtos com quantidade em estoque menor ou igual a 5."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_produtos, {'baixo_estoque': '1'})
        
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camiseta Polo")
        self.assertNotContains(response, "Calça Jeans")

    def test_ordenacao_valida_e_invalida(self):
        """Aplica ordenação permitida e aplica fallback caso receba parâmetro inválido."""
        self.client.force_login(self.superuser)
        
        # Ordem válida
        response = self.client.get(self.url_produtos, {'ordem': 'preco_venda'})
        self.assertEqual(response.status_code, 200)

        # Ordem inválida (deve aplicar o fallback sem quebrar)
        response_invalida = self.client.get(self.url_produtos, {'ordem': 'coluna_proibida'})
        self.assertEqual(response_invalida.status_code, 200)

    def test_cadastrar_produto_com_sucesso(self):
        """Usuário comum cadastra novo produto com sucesso convertendo vírgulas para ponto."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_produtos, {
            'nome': 'Tênis Esportivo',
            'preco_venda': '199,99',
            'preco_custo': '100,00',
            'quantidade_estoque': '10',
            'categoria': 'Calçados'
        })
        self.assertRedirects(response, self.url_produtos)
        
        produto_criado = Produto.objects.filter(nome='Tênis Esportivo', loja=self.loja1).first()
        self.assertIsNotNone(produto_criado)
        self.assertEqual(produto_criado.preco_venda, Decimal('199.99'))

    def test_cadastrar_produto_sem_nome_exibe_erro(self):
        """Tentar cadastrar produto sem o campo nome exibe mensagem de erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_produtos, {
            'nome': '',
            'preco_venda': '50.00'
        })
        self.assertRedirects(response, self.url_produtos)

    def test_cadastrar_produto_valores_numericos_invalidos(self):
        """Enviar preços ou estoque mal formatados exibe mensagem de erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_produtos, {
            'nome': 'Produto Errado',
            'preco_venda': 'abc',
            'quantidade_estoque': 'xyz'
        })
        self.assertRedirects(response, self.url_produtos)

    def test_erro_validacao_model_ao_cadastrar(self):
        """Captura ValidationError lançado pelo model durante o full_clean do produto."""
        self.client.force_login(self.user_loja1)
        
        err = ValidationError({'preco_venda': ['Preço inválido']})
        with patch('infrastructure.models.produto.Produto.full_clean', side_effect=err):
            response = self.client.post(self.url_produtos, {
                'nome': 'Produto Válido',
                'preco_venda': '10.00'
            })
            self.assertRedirects(response, self.url_produtos)

    def test_filtro_categoria_muito_longo_redireciona_com_erro(self):
        """Filtro de categoria com mais de 100 caracteres exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_produtos, {'categoria': 'a' * 101})
        self.assertRedirects(response, self.url_produtos)

    def test_cadastrar_produto_campos_excedem_tamanho_maximo(self):
        """Enviar dados de cadastro que estouram os limites de tamanho exibe erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_produtos, {
            'nome': 'a' * 151,
            'codigo_interno': '1' * 51,
            'categoria': 'c' * 101
        })
        self.assertRedirects(response, self.url_produtos)

    def test_superuser_sem_loja_contexto_nao_cadastra(self):
        """Superusuário sem loja de contexto associada recebe erro ao tentar cadastrar produto."""
        self.client.force_login(self.superuser)
        response = self.client.post(self.url_produtos, {
            'nome': 'Produto Superuser Sem Loja',
            'preco_venda': '10.00'
        })
        self.assertRedirects(response, self.url_produtos)

    def test_cadastrar_produto_com_upload_de_imagens(self):
        """Cadastra novo produto enviando arquivos de imagem associados via Supabase."""
        self.client.force_login(self.user_loja1)
        
        img_file = SimpleUploadedFile("produto.jpg", b"dados_img", content_type="image/jpeg")

        with patch('interfaces.views.produtos_view.upload_imagem_supabase', return_value="https://exemplo.supabase.co/img.jpg"):
            response = self.client.post(self.url_produtos, {
                'nome': 'Produto Com Imagem',
                'preco_venda': '50.00',
                'imagens': img_file
            })

        self.assertRedirects(response, self.url_produtos)

    def test_erro_generico_ao_cadastrar_produto(self):
        """Captura exceção genérica lançada ao salvar o produto e exibe mensagem de erro."""
        self.client.force_login(self.user_loja1)
        
        with patch('infrastructure.models.produto.Produto.save', side_effect=Exception("Erro de BD")):
            response = self.client.post(self.url_produtos, {
                'nome': 'Produto Exceção',
                'preco_venda': '10.00'
            })
            self.assertRedirects(response, self.url_produtos)

    def test_filtro_por_categoria_valida(self):
        """Filtra produtos corretamente usando o parâmetro de categoria válido."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_produtos, {'categoria': 'Vestuário'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Camiseta Polo")
        self.assertContains(response, "Calça Jeans")

    def test_cadastrar_produto_com_multiplas_imagens(self):
        """Cadastra novo produto enviando múltiplas imagens pelo loop de imagens."""
        self.client.force_login(self.user_loja1)
        
        img1 = SimpleUploadedFile("foto1.jpg", b"dados1", content_type="image/jpeg")
        img2 = SimpleUploadedFile("foto2.jpg", b"dados2", content_type="image/jpeg")

        with patch('interfaces.views.produtos_view.upload_imagem_supabase', side_effect=["url1.jpg", "url2.jpg"]):
            response = self.client.post(self.url_produtos, {
                'nome': 'Produto Multimagens',
                'preco_venda': '80.00',
                'imagens': [img1, img2]
            })

        self.assertRedirects(response, self.url_produtos)
        
        produto_criado = Produto.objects.filter(nome='Produto Multimagens').first()
        self.assertIsNotNone(produto_criado)
        self.assertEqual(ProdutoImagem.objects.filter(produto=produto_criado).count(), 2)