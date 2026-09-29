from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from interfaces.views.login_view import TEMPLATE_LOGIN  # Importa a constante da view

User = get_user_model()


class LoginViewTest(TestCase):

    def setUp(self):
        self.url_login = reverse('login')
        self.url_dashboard = reverse('dashboard')
        self.url_admin = '/admin/'
        self.url_alterar_senha = reverse('alterar_senha')

        self.loja = LojaModel.objects.create(nome_loja="Loja Teste", ativo=True)

        self.username = "testuser"
        self.password = "password123"
        
        # Garante explicitamente deve_trocar_senha=False para os testes padrão
        self.user_comum = User.objects.create_user(
            username=self.username, password=self.password, loja=self.loja, deve_trocar_senha=False
        )
        self.superuser = User.objects.create_superuser(
            username="adminuser", password=self.password, deve_trocar_senha=False
        )

    def test_get_pagina_login_renderiza_corretamente(self):
        """Acessar a página de login via GET retorna status 200 e renderiza o template."""
        response = self.client.get(self.url_login)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TEMPLATE_LOGIN)
        self.assertIn('form', response.context)

    def test_usuario_autenticado_ja_redireciona_dashboard(self):
        """Usuário já logado que acessa a tela de login é redirecionado para o dashboard."""
        self.client.force_login(self.user_comum)
        response = self.client.get(self.url_login)
        self.assertRedirects(response, self.url_dashboard, fetch_redirect_response=False)

    def test_usuario_autenticado_precisa_trocar_senha_redireciona(self):
        """Usuário logado que precisa trocar senha é redirecionado para a alteração de senha."""
        self.user_comum.deve_trocar_senha = True
        self.user_comum.save()

        self.client.force_login(self.user_comum)
        response = self.client.get(self.url_login)
        self.assertRedirects(response, self.url_alterar_senha, fetch_redirect_response=False)

    def test_superuser_autenticado_redireciona_admin(self):
        """Superuser logado que acessa a tela de login é redirecionado para o painel admin."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_login)
        self.assertRedirects(response, self.url_admin, fetch_redirect_response=False)

    def test_login_com_sucesso_usuario_comum(self):
        """Realizar login com credenciais válidas redireciona para o dashboard."""
        response = self.client.post(self.url_login, {
            'username': self.username,
            'password': self.password
        })
        self.assertRedirects(response, self.url_dashboard, fetch_redirect_response=False)
        self.assertTrue(("_auth_user_id" in self.client.session))

    def test_login_com_sucesso_superuser(self):
        """Realizar login com credenciais de superuser redireciona para o admin."""
        response = self.client.post(self.url_login, {
            'username': 'adminuser',
            'password': self.password
        })
        self.assertRedirects(response, self.url_admin, fetch_redirect_response=False)

    def test_login_com_sucesso_deve_trocar_senha(self):
        """Se o usuário precisa trocar a senha, o login o redireciona obrigatoriamente para lá."""
        self.user_comum.deve_trocar_senha = True
        self.user_comum.save()

        response = self.client.post(self.url_login, {
            'username': self.username,
            'password': self.password
        })
        self.assertRedirects(response, self.url_alterar_senha, fetch_redirect_response=False)

    def test_login_com_sucesso_respeita_next_url_valida(self):
        """Se houver um parâmetro 'next' seguro, o login redireciona para ele."""
        destino = self.url_dashboard
        response = self.client.post(f"{self.url_login}?next={destino}", {
            'username': self.username,
            'password': self.password
        })
        self.assertRedirects(response, destino, fetch_redirect_response=False)

    def test_login_com_credenciais_invalidas_exibe_erro(self):
        """Enviar senha incorreta exibe erro no formulário e não autentica."""
        response = self.client.post(self.url_login, {
            'username': self.username,
            'password': 'senha_errada'
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(("_auth_user_id" in self.client.session))
        form = response.context['form']
        self.assertTrue(form.errors)

class LoginComMuitasTentativasTest(TestCase):
    """Regressão (auditoria de 29/09): o login aceitava senhas erradas sem limite."""

    def setUp(self):
        loja = LojaModel.objects.create(nome_loja="Loja Teste", ativo=True)
        User.objects.create_user(username="caixa", password="certa", loja=loja, deve_trocar_senha=False)

    def entrar(self, senha):
        return self.client.post(reverse('login'), {'username': 'caixa', 'password': senha})

    def test_na_quinta_senha_errada_avisa_e_bloqueia_ate_a_certa(self):
        for _ in range(4):
            self.assertContains(self.entrar('errada'), 'Usuário ou senha inválidos.')

        self.assertContains(self.entrar('errada'), 'tente de novo daqui a 15 minutos.')
        bloqueado = self.entrar('certa')
        self.assertContains(bloqueado, 'Muitas tentativas com senha errada.')
        self.assertFalse(bloqueado.wsgi_request.user.is_authenticated)

    def test_no_ultimo_minuto_fala_no_singular(self):
        with patch('interfaces.views.login_view.minutos_bloqueado', return_value=1):
            self.assertContains(self.entrar('errada'), 'daqui a 1 minuto.')

    def test_o_login_do_admin_tambem_bloqueia(self):
        User.objects.create_superuser(username="dono", password="certa", deve_trocar_senha=False)
        for _ in range(5):
            self.client.post('/admin/login/', {'username': 'dono', 'password': 'errada'})

        response = self.client.post('/admin/login/', {'username': 'dono', 'password': 'certa'})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.wsgi_request.user.is_authenticated)
