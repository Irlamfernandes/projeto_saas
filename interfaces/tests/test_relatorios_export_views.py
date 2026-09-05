from decimal import Decimal
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente

User = get_user_model()


class RelatoriosExportViewsTest(TestCase):

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

        self.cliente = Cliente.objects.create(loja=self.loja1, nome="Cliente Teste")

    def test_usuario_sem_loja_recebe_permission_denied_pdf(self):
        """Usuário sem loja recebe 403 ao tentar exportar relatório em PDF."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        url = reverse('exportar_pdf_modular', args=['vendas'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_usuario_sem_loja_recebe_permission_denied_excel(self):
        """Usuário sem loja recebe 403 ao tentar exportar relatório em Excel."""
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        url = reverse('exportar_excel_modular', args=['vendas'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 403)

    def test_tipo_relatorio_invalido_retorna_404_pdf(self):
        """Solicitar tipo de relatório inexistente via PDF retorna 404."""
        self.client.force_login(self.user_loja1)
        url = reverse('exportar_pdf_modular', args=['tipo_inexistente'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    def test_tipo_relatorio_invalido_retorna_404_excel(self):
        """Solicitar tipo de relatório inexistente via Excel retorna 404."""
        self.client.force_login(self.user_loja1)
        url = reverse('exportar_excel_modular', args=['tipo_inexistente'])
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)

    @patch('interfaces.views.relatorios_export_views.gerar_relatorio_pdf_secao')
    def test_exportar_pdf_com_sucesso_usuario_comum(self, mock_gerar_pdf):
        """Usuário comum exporta relatório PDF válido de sua loja."""
        self.client.force_login(self.user_loja1)
        url = reverse('exportar_pdf_modular', args=['estoque'])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('attachment; filename="relatorio_estoque.pdf"', response['Content-Disposition'])
        mock_gerar_pdf.assert_called_once()

    @patch('interfaces.views.relatorios_export_views.gerar_relatorio_excel_secao')
    def test_exportar_excel_com_sucesso_superuser(self, mock_gerar_excel):
        """Superusuário exporta relatório Excel consolidado de todas as lojas."""
        self.client.force_login(self.superuser)
        url = reverse('exportar_excel_modular', args=['financeiro'])
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('attachment; filename="relatorio_financeiro.xlsx"', response['Content-Disposition'])
        mock_gerar_excel.assert_called_once()

    @patch('interfaces.views.relatorios_export_views.gerar_relatorio_pdf_secao')
    def test_exportar_pdf_respeita_filtros_data(self, mock_gerar_pdf):
        """Exportação de PDF processa parâmetros de filtro de data enviados na query string."""
        self.client.force_login(self.user_loja1)
        url = reverse('exportar_pdf_modular', args=['vendas'])
        response = self.client.get(url, {'data_inicio': '2026-01-01', 'data_fim': '2026-12-31'})
        
        self.assertEqual(response.status_code, 200)
        mock_gerar_pdf.assert_called_once()

    @patch('interfaces.views.relatorios_export_views.gerar_relatorio_pdf_secao')
    def test_exportar_pdf_ignora_datas_com_formato_invalido(self, mock_gerar_pdf):
        """Parâmetros de data mal formatados geram ValueError e são ignorados silenciosamente."""
        self.client.force_login(self.user_loja1)
        url = reverse('exportar_pdf_modular', args=['vendas'])
        # Envia strings que quebram o datetime.strptime ('%Y-%m-%d')
        response = self.client.get(url, {'data_inicio': 'data-errada', 'data_fim': '31/12/2026'})
        
        self.assertEqual(response.status_code, 200)
        mock_gerar_pdf.assert_called_once()