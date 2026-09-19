from django.test import TestCase, Client
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.usuario_model import UsuarioModel

class ContaViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.loja = LojaModel.objects.create(nome_loja="Loja Teste Conta")
        self.usuario = UsuarioModel.objects.create_user(
            username="usuario_teste",
            password="password123",
            loja=self.loja
        )
        self.url_conta = reverse('conta')

    def test_acesso_nao_autenticado_redireciona(self):
        """Usuário deslogado deve ser redirecionado para o login."""
        response = self.client.get(self.url_conta)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_acesso_autenticado_exibe_conta(self):
        """Usuário autenticado visualiza a página da conta com sucesso."""
        self.client.force_login(self.usuario)
        response = self.client.get(self.url_conta)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interfaces/conta.html')
        self.assertEqual(response.context['loja'], self.loja)