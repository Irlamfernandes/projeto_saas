from datetime import timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto
from infrastructure.models.venda import Venda

User = get_user_model()


class DashboardViewTest(TestCase):

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

        # Cadastros para a Loja 1
        self.cliente_l1 = Cliente.objects.create(loja=self.loja1, nome="Cliente Loja 1")
        self.produto_l1_baixo = Produto.objects.create(
            loja=self.loja1, nome="Produto Escasso", preco_venda=10.0, quantidade_estoque=2
        )
        self.produto_l1_normal = Produto.objects.create(
            loja=self.loja1, nome="Produto Normal", preco_venda=20.0, quantidade_estoque=15
        )

        agora = timezone.now()
        self.venda_l1_hoje = Venda.objects.create(
            loja=self.loja1, cliente=self.cliente_l1, valor_total=100.0, data_venda=agora
        )

        # Cadastros para a Loja 2
        self.cliente_l2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Loja 2")
        self.produto_l2 = Produto.objects.create(
            loja=self.loja2, nome="Produto Outra Loja", preco_venda=50.0, quantidade_estoque=1
        )
        self.venda_l2 = Venda.objects.create(
            loja=self.loja2, cliente=self.cliente_l2, valor_total=300.0, data_venda=agora
        )

        self.url_dashboard = reverse('dashboard')

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar o dashboard."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self.url_dashboard)
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_visualiza_dados_apenas_da_sua_loja(self):
        """Usuário comum vê métricas e totais estritamente da sua loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_dashboard)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_produtos'], 2)
        self.assertEqual(response.context['total_clientes'], 1)
        self.assertEqual(response.context['total_geral'], 100.0)
        self.assertEqual(response.context['vendas_hoje'], 100.0)

    def test_superuser_visualiza_dados_de_todas_as_lojas(self):
        """Superusuário vê a soma de métricas e cadastros de todas as lojas."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_dashboard)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_produtos'], 3)
        self.assertEqual(response.context['total_clientes'], 2)
        self.assertEqual(response.context['total_geral'], 400.0) # 100 + 300
        self.assertEqual(response.context['vendas_hoje'], 400.0)

    def test_filtro_limite_estoque_customizado(self):
        """Parâmetro GET 'limite_estoque' filtra corretamente os produtos com baixo estoque."""
        self.client.force_login(self.user_loja1)

        # Com limite padrão (5), apenas 'Produto Escasso' (estoque 2) deve aparecer
        response = self.client.get(self.url_dashboard)
        baixos = response.context['produtos_baixo_estoque']
        self.assertIn(self.produto_l1_baixo, baixos)
        self.assertNotIn(self.produto_l1_normal, baixos)

        # Alterando limite para 20, ambos devem aparecer
        response_custom = self.client.get(self.url_dashboard, {'limite_estoque': 20})
        baixos_custom = response_custom.context['produtos_baixo_estoque']
        self.assertEqual(baixos_custom.count(), 2)

    def test_filtro_limite_estoque_invalido_usa_fallback(self):
        """Parâmetro GET 'limite_estoque' inválido não quebra a view e assume o padrão (5)."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_dashboard, {'limite_estoque': 'abc'})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['limite_estoque'], 5)

    def test_calculo_vendas_por_periodos_antigos(self):
        """Verifica se vendas em períodos anteriores são somadas corretamente nas faixas correspondentes."""
        agora = timezone.now()

        # Venda antiga (ex: 10 dias atrás -> entra na quinzena, mês, bimestre, trimestre, ano e total geral)
        Venda.objects.create(
            loja=self.loja1,
            cliente=self.cliente_l1,
            valor_total=250.0,
            data_venda=agora - timedelta(days=10)
        )

        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_dashboard)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['vendas_hoje'], 100.0)
        self.assertEqual(response.context['vendas_quinzena'], 350.0) # 100 (hoje) + 250 (10 dias atrás)
        self.assertEqual(response.context['total_geral'], 350.0)
