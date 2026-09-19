from decimal import Decimal
from unittest.mock import patch, MagicMock
from django.test import TestCase
from requests.exceptions import RequestException
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.fatura_assinatura import FaturaAssinatura
from infrastructure.utils.pagamento_pix import criar_cobranca_pix_mercadopago


class PagamentoPixUtilsTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(
            nome_loja="Loja Teste Pix"
        )
        self.fatura = FaturaAssinatura.objects.create(
            loja=self.loja,
            plano='1_MES',
            valor=Decimal('70.00'),
            status='PENDENTE'
        )

    @patch('infrastructure.utils.pagamento_pix.requests.post')
    def test_criar_cobranca_pix_sucesso(self, mock_post):
        """Deve retornar sucesso e os dados do Pix quando a API do Mercado Pago responder corretamente."""
        # Mock da resposta bem-sucedida do Mercado Pago
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.json.return_value = {
            "id": 123456789,
            "point_of_interaction": {
                "transaction_data": {
                    "qr_code": "00020126580014br.gov.bcb.pix...",
                    "qr_code_base64": "data:image/png;base64,iVBORw0KGgo..."
                }
            }
        }
        mock_post.return_value = mock_response

        resultado = criar_cobranca_pix_mercadopago(self.fatura)

        self.assertTrue(resultado["sucesso"])
        self.assertEqual(resultado["id_transacao"], "123456789")
        self.assertEqual(resultado["qr_code_pix"], "00020126580014br.gov.bcb.pix...")
        self.assertEqual(resultado["qr_code_imagem_url"], "data:image/png;base64,iVBORw0KGgo...")
        mock_post.assert_called_once()

    @patch('infrastructure.utils.pagamento_pix.requests.post')
    def test_criar_cobranca_pix_erro_api(self, mock_post):
        """Deve retornar falha quando a API do Mercado Pago retornar erro (ex: 400 Bad Request)."""
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.json.return_value = {
            "message": "Invalid parameter transaction_amount"
        }
        mock_post.return_value = mock_response

        resultado = criar_cobranca_pix_mercadopago(self.fatura)

        self.assertFalse(resultado["sucesso"])
        self.assertEqual(resultado["erro"], "Invalid parameter transaction_amount")

    @patch('infrastructure.utils.pagamento_pix.requests.post')
    def test_criar_cobranca_pix_excecao_conexao(self, mock_post):
        """Deve tratar exceções de rede (RequestException) e retornar falha com a mensagem de erro."""
        mock_post.side_effect = RequestException("Erro de conexão com o servidor")

        resultado = criar_cobranca_pix_mercadopago(self.fatura)

        self.assertFalse(resultado["sucesso"])
        self.assertEqual(resultado["erro"], "Erro de conexão com o servidor")