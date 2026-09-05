from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from interfaces.views.alterar_senha_view import TEMPLATE_ALTERAR_SENHA

User = get_user_model()


class AlterarSenhaViewTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja Teste", ativo=True)
        
        # Usuário que precisa trocar a senha
        self.user_troca = User.objects.create_user(
            username="user_troca", 
            password="old_password123", 
            loja=self.loja,
            deve_trocar_senha=True
        )
        
        # Usuário que NÃO precisa trocar a senha
        self.user_normal = User.objects.create_user(
            username="user_normal", 
            password="old_password123", 
            loja=self.loja,
            deve_trocar_senha=False
        )
        
        self.url_alterar_senha = reverse('alterar_senha')
        self.url_dashboard = reverse('dashboard')

    def test_acesso_nao_autenticado_redireciona(self):
        """Usuário não logado deve ser redirecionado para o login."""
        response = self.client.get(self.url_alterar_senha)
        self.assertNotEqual(response.status_code, 200)

    def test_usuario_sem_obrigatoriedade_troca_redireciona_dashboard(self):
        """Se o usuário não precisa trocar senha, é redirecionado para o dashboard."""
        self.client.force_login(self.user_normal)
        response = self.client.get(self.url_alterar_senha)
        self.assertRedirects(response, self.url_dashboard)

    def test_get_renderiza_pagina_corretamente(self):
        """Usuário com obrigatoriedade de troca consegue ver a página de alteração."""
        self.client.force_login(self.user_troca)
        response = self.client.get(self.url_alterar_senha)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TEMPLATE_ALTERAR_SENHA)

    def test_post_senhas_vazias_retorna_erro(self):
        """POST com campos de senha vazios deve exibir erro."""
        self.client.force_login(self.user_troca)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': '',
            'confirmacao_senha': ''
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any("não podem estar vazios" in str(m) for m in messages))

    def test_post_senhas_excedem_tamanho_maximo(self):
        """POST com senha maior que 128 caracteres deve exibir erro."""
        self.client.force_login(self.user_troca)
        senha_longa = 'a' * 129
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': senha_longa,
            'confirmacao_senha': senha_longa
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any("excede o limite máximo" in str(m) for m in messages))

    def test_post_senhas_nao_coincidem(self):
        """POST com senhas diferentes nos campos exibe erro."""
        self.client.force_login(self.user_troca)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': 'NovaSenhaSegura123!',
            'confirmacao_senha': 'OutraSenhaDiferente123!'
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(any("não coincidem" in str(m) for m in messages))

    def test_post_senha_fraca_rejeitada_pelo_validador(self):
        """POST com senha muito fraca (ex: '123') é rejeitada pelo validate_password."""
        self.client.force_login(self.user_troca)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': '123',
            'confirmacao_senha': '123'
        })
        self.assertEqual(response.status_code, 200)
        messages = list(response.context['messages'])
        self.assertTrue(len(messages) > 0)

    def test_post_sucesso_altera_senha_e_redireciona(self):
        """POST com dados válidos altera a senha com sucesso, atualiza flag e sessão."""
        self.client.force_login(self.user_troca)
        response = self.client.post(self.url_alterar_senha, {
            'nova_senha': 'NovaSenhaForte@2026',
            'confirmacao_senha': 'NovaSenhaForte@2026'
        })
        
        self.assertRedirects(response, self.url_dashboard)
        
        self.user_troca.refresh_from_db()
        self.assertFalse(self.user_troca.deve_trocar_senha)
        self.assertTrue(self.user_troca.check_password('NovaSenhaForte@2026'))