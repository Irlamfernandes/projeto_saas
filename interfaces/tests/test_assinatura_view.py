from unittest.mock import patch
from django.test import TestCase, Client
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.usuario_model import UsuarioModel
from infrastructure.models.fatura_assinatura import FaturaAssinatura

class AssinaturaViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.loja = LojaModel.objects.create(nome_loja="Loja Teste Assinatura")
        self.usuario = UsuarioModel.objects.create_user(
            username="user_assinatura",
            password="password123",
            loja=self.loja
        )
        self.url_assinatura = reverse('assinatura', kwargs={'loja_id': self.loja.pk})

    def test_acesso_nao_autenticado_redireciona(self):
        """Usuário deslogado é redirecionado ao tentar acessar os planos de assinatura."""
        response = self.client.get(self.url_assinatura)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_acesso_outra_loja_gera_permissao_negada(self):
        """Usuário comum não pode acessar a página de assinatura de outra loja."""
        outra_loja = LojaModel.objects.create(nome_loja="Outra Loja")
        url_outra = reverse('assinatura', kwargs={'loja_id': outra_loja.pk})
        
        self.client.force_login(self.usuario)
        response = self.client.get(url_outra)
        self.assertEqual(response.status_code, 403)

    def test_get_exibe_selecao_planos(self):
        """Método GET exibe corretamente o template de seleção de planos."""
        self.client.force_login(self.usuario)
        response = self.client.get(self.url_assinatura)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interfaces/selecionar_plano.html')
        self.assertIn('planos', response.context)

    @patch('interfaces.views.assinatura_view.criar_cobranca_pix_mercadopago')
    def test_post_cria_fatura_e_exibe_pagar_pix_com_sucesso(self, mock_criar_pix):
        """Método POST com plano válido processa o Pix e exibe a tela de pagamento."""
        mock_criar_pix.return_value = {
            'sucesso': True,
            'id_transacao': '987654321',
            'qr_code_pix': 'pix_copia_e_cola_mock',
            'qr_code_imagem_url': 'base64_img_mock'
        }

        self.client.force_login(self.usuario)
        response = self.client.post(self.url_assinatura, {'plano': '1_MES'})

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interfaces/pagar_pix.html')
        
        # Valida se a fatura foi criada e atualizada no banco
        fatura = FaturaAssinatura.objects.filter(loja=self.loja).first()
        self.assertIsNotNone(fatura)
        self.assertEqual(fatura.status, 'PENDENTE')
        self.assertEqual(fatura.id_transacao_gateway, '987654321')

    def test_post_plano_invalido_redireciona_com_erro(self):
        """Método POST com plano inválido não cria fatura e redireciona de volta."""
        self.client.force_login(self.usuario)
        response = self.client.post(self.url_assinatura, {'plano': 'PLANO_FALSO'})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(FaturaAssinatura.objects.count(), 0)