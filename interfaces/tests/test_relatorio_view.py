from decimal import Decimal
from datetime import date, timedelta
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.venda import Venda

User = get_user_model()


class RelatorioViewTest(TestCase):

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

        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(
                deve_trocar_senha=False,
                username="user_sem_loja", password="password", loja=None
            )

        self.cliente_loja1 = Cliente.objects.create(
            loja=self.loja1, nome="Cliente Teste"
        )

        hoje = timezone.now()
        self.venda_hoje = Venda.objects.create(
            loja=self.loja1, cliente=self.cliente_loja1, valor_total=Decimal('200.00'), data_venda=hoje
        )

        data_antiga = hoje - timedelta(days=15)
        self.venda_antiga = Venda.objects.create(
            loja=self.loja1, cliente=self.cliente_loja1, valor_total=Decimal('100.00'), data_venda=data_antiga
        )

        self.venda_loja2 = Venda.objects.create(
            loja=self.loja2, valor_total=Decimal('500.00'), data_venda=hoje
        )

        # Mapeia diretamente para a rota 'relatorios' configurada no seu urls.py
        self.url_relatorio = reverse('relatorios')

    def test_usuario_sem_loja_recebe_permission_denied(self):
        """Usuário comum sem loja associada recebe 403 ao acessar a view de relatórios."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        response = self.client.get(self.url_relatorio)
        self.assertEqual(response.status_code, 403)

    def test_usuario_comum_ve_apenas_dados_da_sua_loja(self):
        """Usuário comum visualiza apenas os relatórios e métricas da sua respectiva loja."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_relatorio)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_geral_vendas'], Decimal('300.00'))

    def test_superuser_ve_dados_de_todas_as_lojas(self):
        """Superusuário visualiza a somatória e dados consolidados de todas as lojas."""
        self.client.force_login(self.superuser)
        response = self.client.get(self.url_relatorio)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_geral_vendas'], Decimal('800.00'))

    def test_filtrar_relatorio_por_data(self):
        """Filtra as vendas do relatório com base nas datas de início e fim fornecidas."""
        self.client.force_login(self.user_loja1)

        hoje_str = date.today().strftime('%Y-%m-%d')
        response = self.client.get(self.url_relatorio, {
            'data_inicio': hoje_str,
            'data_fim': hoje_str
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_geral_vendas'], Decimal('200.00'))

    def test_filtrar_relatorio_com_datas_invalidas(self):
        """Ignora strings de datas inválidas sem quebrar a execução da view."""
        self.client.force_login(self.user_loja1)
        response = self.client.get(self.url_relatorio, {
            'data_inicio': 'data-errada',
            'data_fim': '99/99/9999'
        })

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['total_geral_vendas'], Decimal('300.00'))
