from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models import LojaModel


class OlhinhoDaSenhaTest(TestCase):
    """O script do olhinho (static/js/mostrar_senha.js) carrega em toda tela com campo de senha, no site e no admin."""

    def assertCarregaOOlhinho(self, resposta):
        self.assertContains(resposta, 'js/mostrar_senha.js')
        self.assertContains(resposta, 'css/mostrar_senha.css')
        self.assertContains(resposta, 'type="password"')

    def test_site_e_admin(self):
        self.assertCarregaOOlhinho(self.client.get(reverse('login')))
        self.assertCarregaOOlhinho(self.client.get('/admin/login/'))

        loja = LojaModel.objects.create(nome_loja="Loja A")
        usuario = get_user_model().objects.create_user(username='dono', password='senha-123', loja=loja)
        self.client.force_login(usuario)  # senha temporária: cai na troca obrigatória de senha
        self.assertCarregaOOlhinho(self.client.get(reverse('alterar_senha')))
