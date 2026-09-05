from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel

User = get_user_model()


class ClienteEditarViewTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        self.superuser = User.objects.create_superuser(
            username="admin", password="password"
        )
        self.user_loja1 = User.objects.create_user(
            username="user_loja1", password="password", loja=self.loja1
        )
        
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                username="user_sem_loja", password="password", loja=None
            )

        self.cliente_loja1 = Cliente.objects.create(
            loja=self.loja1, 
            nome="Cliente Antigo", 
            telefone="11999999999", 
            email="antigo@email.com"
        )
        self.cliente_loja2 = Cliente.objects.create(
            loja=self.loja2, 
            nome="Cliente Outra Loja"
        )

        self.url_clientes = reverse('clientes')

    def _get_url_editar(self, pk):
        return reverse('editar_cliente', args=[pk])

    def test_usuario_sem_loja_nem_superuser_recebe_permission_denied(self):
        """Usuário sem loja e sem privilégios administrativos recebe PermissionDenied."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.post(self._get_url_editar(self.cliente_loja1.pk), {'nome': 'Novo Nome'})
        self.assertEqual(response.status_code, 403)

    def test_get_request_redireciona_para_clientes(self):
        """Requisição GET para edição redireciona diretamente para a listagem."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self._get_url_editar(self.cliente_loja1.pk))
        self.assertRedirects(response, self.url_clientes)

    def test_usuario_comum_edita_cliente_da_propria_loja(self):
        """Usuário comum consegue editar cliente pertencente à sua loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.cliente_loja1.pk), {
            'nome': 'Cliente Atualizado',
            'telefone': '11888888888',
            'email': 'novo@email.com',
            'endereco': 'Rua Teste, 123'
        })
        self.assertRedirects(response, self.url_clientes)
        
        self.cliente_loja1.refresh_from_db()
        self.assertEqual(self.cliente_loja1.nome, 'Cliente Atualizado')
        self.assertEqual(self.cliente_loja1.telefone, '11888888888')

    def test_usuario_comum_nao_edita_cliente_de_outra_loja(self):
        """Usuário comum recebe 404 ao tentar editar cliente de outra loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.cliente_loja2.pk), {
            'nome': 'Tentativa Invasão'
        })
        self.assertEqual(response.status_code, 404)

    def test_superuser_edita_cliente_de_qualquer_loja(self):
        """Superusuário consegue editar clientes de qualquer loja."""
        self.client.force_login(self.superuser)
        response = self.client.post(self._get_url_editar(self.cliente_loja2.pk), {
            'nome': 'Editado pelo Admin'
        })
        self.assertRedirects(response, self.url_clientes)
        
        self.cliente_loja2.refresh_from_db()
        self.assertEqual(self.cliente_loja2.nome, 'Editado pelo Admin')

    def test_post_nome_vazio_exibe_erro(self):
        """Enviar formulário com nome vazio não altera o cliente e exibe erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.cliente_loja1.pk), {
            'nome': ''
        })
        self.assertRedirects(response, self.url_clientes)
        
        self.cliente_loja1.refresh_from_db()
        self.assertEqual(self.cliente_loja1.nome, 'Cliente Antigo')

    def test_post_campos_excedem_tamanho_maximo(self):
        """Enviar dados que estouram os limites de tamanho exibe erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self._get_url_editar(self.cliente_loja1.pk), {
            'nome': 'a' * 256,  
            'telefone': '1' * 21  
        })
        self.assertRedirects(response, self.url_clientes)

    def test_erro_validacao_model_capturado(self):
        """Simula erro de validação do modelo durante a limpeza dos dados."""
        self.client.force_login(self.user_loja1)
        
        err = ValidationError({'nome': ['Erro de validação']})
        with patch('infrastructure.models.cliente.Cliente.full_clean', side_effect=err):
            response = self.client.post(self._get_url_editar(self.cliente_loja1.pk), {
                'nome': 'Nome Válido'
            })
            self.assertRedirects(response, self.url_clientes)