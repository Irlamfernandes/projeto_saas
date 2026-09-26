import io
from datetime import datetime
from decimal import Decimal
from unittest.mock import patch
import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from infrastructure.models import Cliente, LojaModel, Venda

User = get_user_model()


class RelatoriosExportViewsTest(TestCase):

    def setUp(self):
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)
        self.superuser = User.objects.create_superuser(username="admin", password="password")
        self.user_loja1 = User.objects.create_user(username="user_loja1", password="password", loja=self.loja1)
        with patch('django.db.models.Model.full_clean'):
            self.user_sem_loja = User.objects.create_user(username="user_sem_loja", password="password", loja=None)

        self.cliente = Cliente.objects.create(loja=self.loja1, nome="Cliente Alpha")
        cliente2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Beta")
        self._venda(self.loja1, self.cliente, '100.00', dia=5)
        self._venda(self.loja1, self.cliente, '50.00', dia=20)
        self._venda(self.loja2, cliente2, '999.00', dia=5)

    def _venda(self, loja, cliente, valor, dia):
        data = timezone.make_aware(datetime(2026, 1, dia, 12, 0))
        Venda.objects.create(loja=loja, cliente=cliente, valor_total=Decimal(valor), data_venda=data)

    def _excel(self, tipo, usuario=None, **params):
        self.client.force_login(usuario or self.user_loja1)
        response = self.client.get(reverse('exportar_excel_modular', args=[tipo]), params)
        self.assertEqual(response.status_code, 200)
        return openpyxl.load_workbook(io.BytesIO(b"".join(response.streaming_content)))

    def test_usuario_sem_loja_recebe_403(self):
        with patch('django.db.models.Model.full_clean'):
            self.client.force_login(self.user_sem_loja)
        for nome in ('exportar_pdf_modular', 'exportar_excel_modular'):
            with self.subTest(nome):
                self.assertEqual(self.client.get(reverse(nome, args=['geral'])).status_code, 403)

    def test_tipo_invalido_retorna_404(self):
        """Tipos antes aceitos mas sem conteúdo ('vendas', 'financeiro'...) agora também são 404."""
        self.client.force_login(self.user_loja1)
        for tipo in ('inexistente', 'vendas', 'financeiro', 'clientes'):
            for nome in ('exportar_pdf_modular', 'exportar_excel_modular'):
                with self.subTest(tipo=tipo, formato=nome):
                    self.assertEqual(self.client.get(reverse(nome, args=[tipo])).status_code, 404)

    def test_pdf_para_download(self):
        self.client.force_login(self.user_loja1)
        response = self.client.get(reverse('exportar_pdf_modular', args=[' Geral ']))

        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertIn('filename="relatorio_geral.pdf"', response['Content-Disposition'])
        self.assertTrue(b"".join(response.streaming_content).startswith(b"%PDF"))

    def test_excel_para_download(self):
        self.client.force_login(self.user_loja1)
        response = self.client.get(reverse('exportar_excel_modular', args=['resumo']))

        self.assertEqual(response['Content-Type'], 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.assertIn('filename="relatorio_resumo.xlsx"', response['Content-Disposition'])

    def test_exporta_apenas_dados_da_loja_do_usuario(self):
        faturamento = self._excel('resumo').active['B2'].value
        self.assertEqual(faturamento, 150)

    def test_superuser_exporta_todas_as_lojas(self):
        self.assertEqual(self._excel('resumo', usuario=self.superuser).active['B2'].value, 1149)

    def test_respeita_o_filtro_de_datas(self):
        planilha = self._excel('resumo', data_inicio='2026-01-10', data_fim='2026-01-31')
        self.assertEqual(planilha.active['B2'].value, 50)

    def test_datas_malformadas_sao_ignoradas(self):
        planilha = self._excel('resumo', data_inicio='2026-13-45', data_fim='xyz')
        self.assertEqual(planilha.active['B2'].value, 150)
