from django.contrib.messages import get_messages
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel
from interfaces.views.clientes_view import TEMPLATE_CLIENTES  # Importa a constante da view

User = get_user_model()


class ClientesViewTest(TestCase):

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

        # Cria usuário sem loja ignorando o full_clean do model para teste de permissão
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                deve_trocar_senha=False,
                username="user_sem_loja", password="password", loja=None
            )

        self.cliente_loja1 = Cliente.objects.create(
            loja=self.loja1,
            nome="Carlos Silva",
            telefone="11988887777",
            email="carlos@email.com"
        )
        self.cliente_loja2 = Cliente.objects.create(
            loja=self.loja2,
            nome="Ana Souza",
            telefone="21977776666"
        )

        self.url_clientes = reverse('clientes')

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar a listagem."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self.url_clientes)
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_ve_apenas_clientes_da_sua_loja(self):
        """Usuário comum visualiza somente os clientes pertencentes à sua loja e valida template."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_clientes)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, TEMPLATE_CLIENTES)
        self.assertContains(response, "Carlos Silva")
        self.assertNotContains(response, "Ana Souza")

    def test_superuser_ve_todos_os_clientes(self):
        """Superusuário visualiza clientes de todas las lojas."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_clientes)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carlos Silva")
        self.assertContains(response, "Ana Souza")

    def test_busca_por_nome_ou_telefone(self):
        """Filtra clientes corretamente usando o parâmetro de busca 'q'."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_clientes, {'q': 'Carlos'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Carlos Silva")
        self.assertNotContains(response, "Ana Souza")

    def test_busca_muito_longa_redireciona_com_erro(self):
        """Busca com mais de 100 caracteres exibe mensagem de erro e redireciona."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_clientes, {'q': 'a' * 101})
        self.assertRedirects(response, self.url_clientes)

    def test_cadastrar_cliente_com_sucesso(self):
        """Usuário comum cadastra novo cliente com sucesso na sua loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_clientes, {
            'nome': 'Novo Cliente',
            'telefone': '11912345678',
            'email': 'novo@email.com',
            'endereco': 'Rua Teste, 456'
        })
        self.assertRedirects(response, self.url_clientes)
        self.assertTrue(Cliente.objects.filter(nome='Novo Cliente', loja=self.loja1).exists())

    def test_cadastrar_cliente_sem_nome_exibe_erro(self):
        """Tentar cadastrar cliente sem o campo nome exibe mensagem de erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_clientes, {
            'nome': '',
            'telefone': '11912345678'
        })
        self.assertRedirects(response, self.url_clientes)
        self.assertFalse(Cliente.objects.filter(telefone='11912345678').exists())

    def test_cadastrar_cliente_com_campos_excedendo_limite(self):
        """Cadastrar dados que estouram os limites de tamanho gera erro."""
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_clientes, {
            'nome': 'a' * 256,
            'telefone': '1' * 21
        })
        self.assertRedirects(response, self.url_clientes)

    def test_erro_validacao_model_ao_cadastrar(self):
        """Captura ValidationError lançado pelo model durante o cadastro."""
        self.client.force_login(self.user_loja1)

        err = ValidationError({'nome': ['Erro customizado']})
        with patch('infrastructure.models.cliente.Cliente.full_clean', side_effect=err):
            response = self.client.post(self.url_clientes, {
                'nome': 'Cliente Valido'
            })
            self.assertRedirects(response, self.url_clientes)

    def test_usuario_sem_loja_nao_pode_cadastrar_cliente(self):
        """Usuário comum sem loja associada recebe 403 ao tentar criar um cliente."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.post(self.url_clientes, {
            'nome': 'Cliente Sem Loja'
        })
        self.assertEqual(response.status_code, 403)


    def _mensagens(self, response):
        return [str(m) for m in get_messages(response.wsgi_request)]

    def test_cadastrar_cliente_so_com_nome(self):
        """Regressão: cadastrar sem e-mail/telefone/endereço gerava HTTP 500 (NOT NULL)."""
        self.client.force_login(self.user_loja1)

        response = self.client.post(self.url_clientes, {'nome': 'Só Nome', 'telefone': '', 'email': '', 'endereco': ''})

        self.assertRedirects(response, self.url_clientes)
        self.assertEqual(self._mensagens(response), ["Cliente cadastrado com sucesso!"])
        self.assertEqual(Cliente.objects.get(nome='Só Nome').email, '')

    def test_cadastro_invalido_informa_o_motivo(self):
        self.client.force_login(self.user_loja1)
        response = self.client.post(self.url_clientes, {'nome': 'Ana', 'email': 'invalido'})
        self.assertEqual(self._mensagens(response), ["Informe um e-mail válido."])

    def test_superuser_sem_loja_nao_cadastra(self):
        self.client.force_login(self.superuser)
        response = self.client.post(self.url_clientes, {'nome': 'Cliente do Admin'})

        self.assertEqual(self._mensagens(response), ["Superusuários devem associar o cliente a uma loja específica."])
        self.assertFalse(Cliente.objects.filter(nome='Cliente do Admin').exists())
