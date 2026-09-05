import io
from unittest.mock import patch, MagicMock
from django.test import TestCase
from requests.exceptions import RequestException
from infrastructure.utils.supabase_storage import (
    limpar_nome_arquivo,
    upload_imagem_supabase
)


class SupabaseStorageTest(TestCase):

    def test_limpar_nome_arquivo(self):
        """Testa a remoção de acentos e formatação de nomes de arquivos."""
        nome_sujo = "Foto de Produto com Çaracteres & Acentuação.jpg"
        nome_limpo = limpar_nome_arquivo(nome_sujo)
        self.assertEqual(nome_limpo, "Foto_de_Produto_com_Caracteres_&_Acentuacao.jpg")

    @patch('infrastructure.utils.supabase_storage.SUPABASE_URL', None)
    @patch('infrastructure.utils.supabase_storage.SUPABASE_KEY', 'some_key')
    def test_upload_missing_url_raises_exception(self):
        """Deve lançar exceção se a URL do Supabase não estiver configurada."""
        file_obj = io.BytesIO(b"conteudo")
        file_obj.name = "teste.jpg"

        with self.assertRaises(Exception) as ctx:
            upload_imagem_supabase(file_obj, produto_id=1)
        self.assertIn("Credenciais do Supabase não configuradas", str(ctx.exception))

    @patch('infrastructure.utils.supabase_storage.SUPABASE_KEY', None)
    @patch('infrastructure.utils.supabase_storage.SUPABASE_URL', 'https://xyz.supabase.co')
    def test_upload_missing_key_raises_exception(self):
        """Deve lançar exceção se a Key do Supabase não estiver configurada."""
        file_obj = io.BytesIO(b"conteudo")
        file_obj.name = "teste.jpg"

        with self.assertRaises(Exception) as ctx:
            upload_imagem_supabase(file_obj, produto_id=1)
        self.assertIn("Credenciais do Supabase não configuradas", str(ctx.exception))

    @patch('infrastructure.utils.supabase_storage.SUPABASE_KEY', 'test_key')
    @patch('infrastructure.utils.supabase_storage.SUPABASE_URL', 'https://xyz.supabase.co/rest/v1')
    @patch('infrastructure.utils.supabase_storage.requests.post')
    def test_upload_success(self, mock_post):
        """Realiza o upload com sucesso e retorna a URL pública."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        file_obj = io.BytesIO(b"imagem_bytes")
        file_obj.name = "foto capivara.jpg"
        file_obj.content_type = "image/jpeg"

        url_publica = upload_imagem_supabase(file_obj, produto_id=10)

        self.assertTrue(mock_post.called)
        self.assertEqual(
            url_publica, 
            "https://xyz.supabase.co/storage/v1/object/public/produtos/10/foto_capivara.jpg"
        )

    @patch('infrastructure.utils.supabase_storage.SUPABASE_KEY', 'test_key')
    @patch('infrastructure.utils.supabase_storage.SUPABASE_URL', 'https://xyz.supabase.co')
    @patch('infrastructure.utils.supabase_storage.requests.post')
    def test_upload_api_error_status(self, mock_post):
        """Lança exceção se o Supabase retornar um status code de erro (ex: 400)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        file_obj = io.BytesIO(b"dados")
        file_obj.name = "arquivo.jpg"

        with self.assertRaises(Exception) as ctx:
            upload_imagem_supabase(file_obj, produto_id=5)
        self.assertIn("Erro na API do Supabase (400)", str(ctx.exception))

    @patch('infrastructure.utils.supabase_storage.SUPABASE_KEY', 'test_key')
    @patch('infrastructure.utils.supabase_storage.SUPABASE_URL', 'https://xyz.supabase.co')
    @patch('infrastructure.utils.supabase_storage.requests.post')
    def test_upload_request_exception(self, mock_post):
        """Lança exceção se ocorrer um erro de requisição (rede/conexão)."""
        mock_post.side_effect = RequestException("Erro de conexão")

        file_obj = io.BytesIO(b"dados")
        file_obj.name = "arquivo.jpg"

        with self.assertRaises(Exception) as ctx:
            upload_imagem_supabase(file_obj, produto_id=5)
        self.assertIn("Erro no Supabase Storage", str(ctx.exception))