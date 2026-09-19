from django.test import TestCase, Client
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.usuario_model import UsuarioModel

class AlterarSenhaViewTest(TestCase):

    def setUp(self):
        self.client = Client()
        self.loja = LojaModel.objects.create(nome_loja="Loja Teste Senha")
        self.usuario = UsuarioModel.objects.create_user(
            username="user_senha",
            password="old_password123",
            loja=self.loja,
            deve_trocar_senha=True
        )
        self.url_alterar_senha = reverse('alterar_senha')

    def test_acesso_nao_autenticado_redireciona(self):
        """Usuário deslogado é redirecionado ao tentar acessar a alteração de senha."""
        response = self.client.get(self.url_alterar_senha)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_get_exibe_pagina_alterar_senha(self):
        """Usuário autenticado consegue carregar a página de alteração de senha."""
        self.client.force_login(self.usuario)
        response = self.client.get(self.url_alterar_senha)
        
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'interfaces/alterar_senha.html')
        self.assertIn('obrigatorio', response.context)

    def test_post_senhas_nao_coincidem_retorna_erro(self):
        """Tentar alterar a senha com senhas divergentes exibe mensagem de erro."""
        self.client.force_login(self.usuario)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': 'NovaSenhaSegura123',
            'confirmacao_senha': 'OutraSenhaDivergente123'
        })
        
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any("As senhas não coincidem." in str(m) for m in messages))

    def test_post_campos_vazios_retorna_erro(self):
        """Deixar campos de senha vazios retorna erro."""
        self.client.force_login(self.usuario)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': '',
            'confirmacao_senha': ''
        })
        
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any("Os campos de senha não podem estar vazios." in str(m) for m in messages))

    def test_post_senha_alterada_com_sucesso(self):
        """Alterar a senha com dados válidos atualiza o usuário e remove a flag de troca obrigatória."""
        self.client.force_login(self.usuario)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': 'NovaSenhaForte123!',
            'confirmacao_senha': 'NovaSenhaForte123!'
        })

        # Deve redirecionar para o dashboard após sucesso
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('dashboard'))

        # Atualiza a instância do banco para verificar a flag
        self.usuario.refresh_from_db()
        self.assertFalse(self.usuario.deve_trocar_senha)
        self.assertTrue(self.usuario.check_password('NovaSenhaForte123!'))