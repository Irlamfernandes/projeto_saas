from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel

User = get_user_model()


class ExtratoPdfViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(
            deve_trocar_senha=False,
            username="admin", password="password"
        )
        self.user_loja1 = User.objects.create_user(
            deve_trocar_senha=False,
            username="user_loja1", password="password", loja=self.loja1
        )

        # Cria usuário sem loja ignorando o full_clean para testar a exceção de permissão
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                deve_trocar_senha=False,
                username="user_sem_loja", password="password", loja=None
            )

        self.cliente_loja1 = Cliente.objects.create(
            loja=self.loja1, nome="João da Silva & Cia."
        )
        self.cliente_loja2 = Cliente.objects.create(
            loja=self.loja2, nome="Maria Souza"
        )

    def _get_url_pdf(self, cliente_id):
        return reverse('extrato_pdf', args=[cliente_id])

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao tentar gerar o PDF."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self._get_url_pdf(self.cliente_loja1.pk))
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_gera_pdf_cliente_da_propria_loja(self):
        """Usuário comum consegue baixar o extrato em PDF de um cliente da sua própria loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self._get_url_pdf(self.cliente_loja1.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment', response['Content-Disposition'])
        # Verifica se o nome do arquivo foi sanitizado corretamente (espaços e '&' viram '_')
        self.assertIn('extrato_Jo_o_da_Silva___Cia_.pdf', response['Content-Disposition'])

    def test_usuario_comum_nao_gera_pdf_cliente_de_outra_loja(self):
        """Usuário comum recebe 404 ao tentar gerar PDF de cliente pertencente a outra loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self._get_url_pdf(self.cliente_loja2.pk))
        self.assertEqual(response.status_code, 404)

    def test_superuser_gera_pdf_de_qualquer_loja(self):
        """Superusuário consegue gerar o PDF do extrato de clientes de qualquer loja."""
        self.client.force_login(self.superuser)
        response = self.client.get(self._get_url_pdf(self.cliente_loja2.pk))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('extrato_Maria_Souza.pdf', response['Content-Disposition'])
