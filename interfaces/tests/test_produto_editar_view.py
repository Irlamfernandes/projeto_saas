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


class ProdutoEditarViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(
            username="admin", password="password"
        )
        self.user_loja1 = User.objects.create_user(
            username="user_loja1", password="password", loja=self.loja1
        )
        
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                username="user_sem_loja", password="password", loja=None
            )

        self.produto_loja1 = Produto.objects.create(
            loja=self.loja1, 
            nome="Produto Antigo", 
            preco_custo=Decimal('10.00'),
            preco_venda=Decimal('20.00'),
            quantidade_estoque=10
        )
        self.produto_loja2 = Produto.objects.create(
            loja=self.loja2, 
            nome="Produto Outra Loja", 
            preco_custo=Decimal('15.00'),
            preco_venda=Decimal('30.00'),
            quantidade_estoque=5
        )

        self.url_produtos = reverse('produtos')

    def _get_url_editar(self, pk):
        return reverse('editar_produto', args=[pk])

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar a edição do produto."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self._get_url_editar(self.produto_loja1.pk))
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_edita_produto_da_propria_loja(self):
        """Usuário comum consegue editar produto da sua própria loja com sucesso."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
            'nome': 'Produto Atualizado',
            'preco_venda': '25,50',
            'preco_custo': '12.00',
            'quantidade_estoque': '15'
        })
        self.assertRedirects(response, self.url_produtos)
        
        self.produto_loja1.refresh_from_db()
        self.assertEqual(self.produto_loja1.nome, 'Produto Atualizado')
        self.assertEqual(self.produto_loja1.preco_venda, Decimal('25.50'))
        self.assertEqual(self.produto_loja1.quantidade_estoque, 15)

    def test_usuario_comum_nao_edita_produto_de_outra_loja(self):
        """Usuário comum recebe 404 ao tentar editar produto pertencente a outra loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.produto_loja2.pk), {
            'nome': 'Tentativa Invasão'
        })
        self.assertEqual(response.status_code, 404)

    def test_superuser_edita_produto_de_qualquer_loja(self):
        """Superusuário consegue editar produtos de qualquer loja."""
        self.client.force_login(self.superuser)
        response = self.client.post(self._get_url_editar(self.produto_loja2.pk), {
            'nome': 'Editado pelo Admin',
            'preco_venda': '45.00'
        })
        self.assertRedirects(response, self.url_produtos)
        
        self.produto_loja2.refresh_from_db()
        self.assertEqual(self.produto_loja2.nome, 'Editado pelo Admin')

    def test_post_nome_vazio_exibe_erro(self):
        """Enviar formulário com nome vazio não altera o produto e exibe erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
            'nome': ''
        })
        self.assertRedirects(response, self._get_url_editar(self.produto_loja1.pk))
        
        self.produto_loja1.refresh_from_db()
        self.assertEqual(self.produto_loja1.nome, 'Produto Antigo')

    def test_post_valores_numericos_invalidos(self):
        """Enviar preços ou estoque inválidos exibe erro e redireciona de volta para a edição."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
            'nome': 'Produto Válido',
            'preco_venda': 'abc',
            'quantidade_estoque': 'xyz'
        })
        self.assertRedirects(response, self._get_url_editar(self.produto_loja1.pk))

    def test_post_campos_excedem_tamanho_maximo(self):
        """Enviar dados que estouram os limites de tamanho exibe erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
            'nome': 'a' * 151,  
            'codigo_interno': '1' * 51
        })
        self.assertRedirects(response, self._get_url_editar(self.produto_loja1.pk))

    def test_erro_validacao_model_capturado(self):
        """Simula erro de validação do modelo durante a limpeza dos dados do produto."""
        self.client.force_login(self.user_loja1)
        
        err = ValidationError({'preco_venda': ['Preço não pode ser negativo']})
        with patch('infrastructure.models.produto.Produto.full_clean', side_effect=err):
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Válido',
                'preco_venda': '-5.00'
            })
            self.assertRedirects(response, self._get_url_editar(self.produto_loja1.pk))

    def test_editar_produto_com_upload_de_nova_imagem(self):
        """Simula o envio de uma nova imagem para o produto."""
        self.client.force_login(self.user_loja1)
        
        img_file = SimpleUploadedFile("nova_foto.jpg", b"conteudo_foto", content_type="image/jpeg")
        
        with patch('interfaces.views.produto_editar_view.upload_imagem_supabase', return_value="https://exemplo.supabase.co/nova.jpg"):
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Com Foto Nova',
                'preco_venda': '75.00',
                'imagens': img_file
            })

        self.assertRedirects(response, self.url_produtos)

    def test_editar_produto_com_remocao_de_imagem_supabase_com_rest_v1(self):
        """Cobre a remoção de imagem quando SUPABASE_URL termina com /rest/v1."""
        imagem_obj = ProdutoImagem.objects.create(
            produto=self.produto_loja1,
            imagem_url="https://exemplo.supabase.co/storage/v1/object/public/imagens/loja1/foto.jpg"
        )
        self.client.force_login(self.user_loja1)

        with patch.dict('os.environ', {'SUPABASE_URL': 'https://exemplo.supabase.co/rest/v1', 'SUPABASE_KEY': 'fake-key'}):
            with patch('requests.delete') as mock_delete:
                mock_delete.return_value.status_code = 200
                response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                    'nome': 'Produto Sem Imagem Rest V1',
                    'preco_venda': '20.00',
                    'quantidade_estoque': '5',
                    'remover_imagens': str(imagem_obj.id)
                })

        self.assertRedirects(response, self.url_produtos)
        self.assertFalse(ProdutoImagem.objects.filter(pk=imagem_obj.id).exists())

    def test_erro_generico_ao_editar_produto(self):
        """Cobre a captura de exceção genérica (except Exception) ao salvar o produto editado."""
        self.client.force_login(self.user_loja1)
        
        with patch('infrastructure.models.produto.Produto.save', side_effect=Exception("Erro inesperado no BD")):
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Erro Genérico',
                'preco_venda': '10.00',
                'quantidade_estoque': '5'
            })
            self.assertRedirects(response, self._get_url_editar(self.produto_loja1.pk))

    def test_editar_produto_com_remocao_de_imagem(self):
        """Simula a remoção de uma imagem associada ao produto."""
        imagem_obj = ProdutoImagem.objects.create(
            produto=self.produto_loja1,
            imagem_url="https://exemplo.supabase.co/storage/v1/object/public/imagens/loja1/foto.jpg"
        )

        self.client.force_login(self.user_loja1)
        
        with patch('requests.delete') as mock_delete:
            mock_delete.return_value.status_code = 200
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Sem Imagem',
                'preco_venda': '20.00',
                'quantidade_estoque': '10',
                'remover_imagens': str(imagem_obj.id)
            })

        self.assertRedirects(response, self.url_produtos, fetch_redirect_response=False)
        self.assertFalse(ProdutoImagem.objects.filter(pk=imagem_obj.id).exists())

    def test_editar_produto_com_upload_de_novas_imagens_multiplas(self):
        """Cobre explicitamente o loop de upload de novas imagens na edição."""
        self.client.force_login(self.user_loja1)
        img1 = SimpleUploadedFile("edit_foto1.jpg", b"dados1", content_type="image/jpeg")
        
        with patch('interfaces.views.produto_editar_view.upload_imagem_supabase', return_value="https://exemplo.supabase.co/edit1.jpg"):
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Editado Com Imagens',
                'preco_venda': '50.00',
                'quantidade_estoque': '10',
                'imagens': [img1]
            })

        self.assertRedirects(response, self.url_produtos)
        self.assertEqual(ProdutoImagem.objects.filter(produto=self.produto_loja1).count(), 1)

    def test_editar_produto_com_excecao_ao_deletar_imagem_supabase(self):
        """Cobre a captura de exceção (except Exception) ao tentar deletar imagem no Supabase."""
        imagem_obj = ProdutoImagem.objects.create(
            produto=self.produto_loja1,
            imagem_url="https://exemplo.supabase.co/storage/v1/object/public/imagens/loja1/foto_erro.jpg"
        )

        self.client.force_login(self.user_loja1)
        
        with patch('requests.delete', side_effect=Exception("Erro de conexão ao deletar")):
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Erro Deletar Imagem',
                'preco_venda': '20.00',
                'quantidade_estoque': '5',
                'remover_imagens': str(imagem_obj.id)
            })

        self.assertRedirects(response, self.url_produtos)
        self.assertFalse(ProdutoImagem.objects.filter(pk=imagem_obj.id).exists())

    def test_editar_produto_com_valores_numericos_vazios(self):
        """Cobre o envio de campos numéricos como strings vazias para testar os fallbacks."""
        self.client.force_login(self.user_loja1)
        
        with patch('infrastructure.models.produto.Produto.full_clean'):
            response = self.client.post(self._get_url_editar(self.produto_loja1.pk), {
                'nome': 'Produto Valores Vazios',
                'preco_custo': '',
                'preco_venda': '',
                'margem_lucro': '',
                'quantidade_estoque': ''
            })
            
        self.assertRedirects(response, self.url_produtos)

    def test_remover_imagem_supabase_url_vazia(self):
        """Cobre o retorno antecipado (guard clause) quando a URL da imagem é vazia."""
        from interfaces.views.produto_editar_view import _remover_imagem_supabase
        # Não deve lançar exceção nem fazer requisição HTTP
        _remover_imagem_supabase("")
        _remover_imagem_supabase(None)
        self.assertTrue(True)