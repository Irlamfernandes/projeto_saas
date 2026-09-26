from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from interfaces.views.alterar_senha_view import TEMPLATE_ALTERAR_SENHA

User = get_user_model()
SENHA_FORTE = 'Caderneta#Segura2026'


class AlterarSenhaViewTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja Teste", ativo=True)
        self.user_troca = User.objects.create_user(
            username="user_troca", password="temporaria1", loja=self.loja, deve_trocar_senha=True,
        )
        self.user_normal = User.objects.create_user(
            username="user_normal", password="definitiva1", loja=self.loja, deve_trocar_senha=False,
        )
        self.url = reverse('alterar_senha')
        self.url_dashboard = reverse('dashboard')

    def _trocar(self, nova, confirmacao, usuario=None):
        self.client.force_login(usuario or self.user_troca)
        return self.client.post(self.url, {'nova_senha': nova, 'confirmacao_senha': confirmacao})

    def test_anonimo_vai_para_o_login(self):
        """Regressão: sem LOGIN_URL o Django mandava para /accounts/login/, que não existe (404)."""
        response = self.client.get(self.url)
        self.assertRedirects(response, f"{reverse('login')}?next={self.url}", fetch_redirect_response=False)

    def test_troca_obrigatoria_nao_pede_a_senha_atual(self):
        self.client.force_login(self.user_troca)
        response = self.client.get(self.url)

        self.assertTemplateUsed(response, TEMPLATE_ALTERAR_SENHA)
        self.assertContains(response, "Primeiro Acesso")
        self.assertNotContains(response, 'name="senha_atual"')

    # --- troca voluntária -------------------------------------------------

    def test_troca_voluntaria_pede_a_senha_atual(self):
        self.client.force_login(self.user_normal)
        response = self.client.get(self.url)

        self.assertContains(response, "Alterar Senha")
        self.assertContains(response, 'name="senha_atual"')

    def test_troca_voluntaria_com_senha_atual_errada_ou_ausente(self):
        self.client.force_login(self.user_normal)
        casos = {'errada': ('outra-senha', "A senha atual está incorreta."), 'ausente': ('', "Informe sua senha atual.")}
        for caso, (atual, mensagem) in casos.items():
            with self.subTest(caso):
                response = self.client.post(self.url, {
                    'senha_atual': atual, 'nova_senha': SENHA_FORTE, 'confirmacao_senha': SENHA_FORTE,
                })
                self.assertContains(response, mensagem)
                self.user_normal.refresh_from_db()
                self.assertTrue(self.user_normal.check_password('definitiva1'))

    def test_troca_voluntaria_com_sucesso(self):
        self.client.force_login(self.user_normal)
        response = self.client.post(self.url, {
            'senha_atual': 'definitiva1', 'nova_senha': SENHA_FORTE, 'confirmacao_senha': SENHA_FORTE,
        })

        self.assertRedirects(response, self.url_dashboard)
        self.user_normal.refresh_from_db()
        self.assertTrue(self.user_normal.check_password(SENHA_FORTE))

    def test_menu_tem_link_para_alterar_a_senha(self):
        self.client.force_login(self.user_normal)
        self.assertContains(self.client.get(self.url_dashboard), f'href="{self.url}"')

    def test_erros_aparecem_na_pagina(self):
        """Regressão: as mensagens iam para `messages`, que esta página não exibe; o usuário não via o motivo."""
        casos = {
            'vazias': ('', '', "Os campos de senha não podem estar vazios."),
            'longas': ('a' * 129, 'a' * 129, "A senha excede o limite máximo de caracteres permitido."),
            'diferentes': (SENHA_FORTE, SENHA_FORTE + 'x', "As senhas não coincidem."),
            'curta': ('Ab#1', 'Ab#1', "Esta senha é muito curta. Ela precisa conter pelo menos 8 caracteres."),
            'comum': ('password123', 'password123', "Esta senha é muito comum."),
            'só números': ('83920184', '83920184', "Esta senha é inteiramente numérica."),
            'parecida com o usuário': ('user_troca1', 'user_troca1', "A senha é muito parecida com"),
        }
        for caso, (nova, confirmacao, mensagem) in casos.items():
            with self.subTest(caso):
                response = self._trocar(nova, confirmacao)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, mensagem)
                self.user_troca.refresh_from_db()
                self.assertTrue(self.user_troca.deve_trocar_senha)

    def test_mensagem_repetida_aparece_uma_vez(self):
        response = self._trocar('', '')
        self.assertContains(response, "Os campos de senha não podem estar vazios.", count=1)

    def test_troca_com_sucesso(self):
        response = self._trocar(SENHA_FORTE, SENHA_FORTE)

        self.assertRedirects(response, self.url_dashboard)
        self.assertEqual([str(m) for m in get_messages(response.wsgi_request)], ["Senha alterada com sucesso!"])
        self.user_troca.refresh_from_db()
        self.assertFalse(self.user_troca.deve_trocar_senha)
        self.assertTrue(self.user_troca.check_password(SENHA_FORTE))
        self.assertEqual(self.client.get(self.url_dashboard).status_code, 200, "sessão deve continuar válida")

    def test_equipe_vai_para_o_admin_apos_trocar(self):
        admin = User.objects.create_superuser(username="chefe", password="temporaria1")
        self.assertRedirects(self._trocar(SENHA_FORTE, SENHA_FORTE, usuario=admin), '/admin/', fetch_redirect_response=False)

    def test_telas_da_loja_exigem_a_troca(self):
        self.client.force_login(self.user_troca)
        for nome in ('dashboard', 'vendas', 'produtos', 'clientes', 'relatorios'):
            with self.subTest(nome):
                self.assertRedirects(self.client.get(reverse(nome)), self.url, fetch_redirect_response=False)
