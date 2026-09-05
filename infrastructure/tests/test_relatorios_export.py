import os
import tempfile
from decimal import Decimal
import openpyxl
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from infrastructure.models.cliente import Cliente
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto
from infrastructure.utils.relatorios_export import (
    gerar_relatorio_pdf_secao,
    gerar_relatorio_excel_secao,
    gerar_relatorio_pdf,
    gerar_relatorio_excel
)


class RelatoriosExportTest(TestCase):

    def setUp(self):
        # Lojas
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Central", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Secundária", ativo=True)

        # Contexto de dados padrão (mock dict para relatórios)
        self.contexto = {
            'loja': self.loja1,
            'total_geral_vendas': Decimal('1500.00'),
            'ticket_medio': Decimal('150.00'),
            'total_fiado_pendente': Decimal('300.00'),
            'total_credito_clientes': Decimal('50.00'),
            'vendas_hoje_valor': Decimal('200.00'),
            'vendas_semana_valor': Decimal('800.00'),
            'vendas_mes_valor': Decimal('1500.00'),
            'vendas_ano_valor': Decimal('5000.00'),
        }

        # Clientes
        self.cliente_loja1 = Cliente.objects.create(loja=self.loja1, nome="João Devendo")
        self.cliente_loja2 = Cliente.objects.create(loja=self.loja2, nome="Cliente Outra Loja")

        self.contexto['clientes_devendo'] = [self.cliente_loja1, self.cliente_loja2]
        self.contexto['clientes_credito'] = [self.cliente_loja1, self.cliente_loja2]

        # Produtos
        self.prod_loja1 = Produto.objects.create(loja=self.loja1, nome="Caneta", preco_venda=Decimal('2.00'), quantidade_estoque=100)
        self.prod_loja2 = Produto.objects.create(loja=self.loja2, nome="Caderno", preco_venda=Decimal('20.00'), quantidade_estoque=10)

        self.contexto['estoque_ordenado'] = [self.prod_loja1, self.prod_loja2]

        # Arquivos temporários
        self.temp_pdf = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        self.temp_pdf.close()
        self.caminho_pdf = self.temp_pdf.name

        self.temp_excel = tempfile.NamedTemporaryFile(suffix='.xlsx', delete=False)
        self.temp_excel.close()
        self.caminho_excel = self.temp_excel.name

    def tearDown(self):
        for caminho in [self.caminho_pdf, self.caminho_excel]:
            if os.path.exists(caminho):
                os.unlink(caminho)

    # ---------------------------------------------------------
    # Testes de Segurança / Permissão
    # ---------------------------------------------------------
    def test_gerar_relatorio_pdf_permission_denied(self):
        """Deve lançar PermissionDenied se o contexto pertencer a outra loja."""
        with self.assertRaises(PermissionDenied):
            gerar_relatorio_pdf_secao('resumo', self.contexto, self.caminho_pdf, loja_usuario=self.loja2)

    # ---------------------------------------------------------
    # Testes de Geração de PDF por Seção
    # ---------------------------------------------------------
    def test_gerar_pdf_secao_resumo_e_geral(self):
        """Testa geração de PDF para as seções resumo e geral."""
        for tipo in ['resumo', 'geral']:
            gerar_relatorio_pdf_secao(tipo, self.contexto, self.caminho_pdf, loja_usuario=self.loja1)
            self.assertTrue(os.path.exists(self.caminho_pdf))
            self.assertGreater(os.path.getsize(self.caminho_pdf), 0)

    def test_gerar_pdf_secao_temporal(self):
        """Testa geração de PDF para a seção temporal."""
        gerar_relatorio_pdf_secao('temporal', self.contexto, self.caminho_pdf, loja_usuario=self.loja1)
        self.assertTrue(os.path.exists(self.caminho_pdf))

    def test_gerar_pdf_secao_devendo_e_credito(self):
        """Testa geração de PDF para clientes devendo e com crédito (com filtro de loja)."""
        gerar_relatorio_pdf_secao('devendo', self.contexto, self.caminho_pdf, loja_usuario=self.loja1)
        gerar_relatorio_pdf_secao('credito', self.contexto, self.caminho_pdf, loja_usuario=self.loja1)
        self.assertTrue(os.path.exists(self.caminho_pdf))

    def test_gerar_pdf_secao_estoque(self):
        """Testa geração de PDF para o inventário de estoque."""
        gerar_relatorio_pdf_secao('estoque', self.contexto, self.caminho_pdf, loja_usuario=self.loja1)
        self.assertTrue(os.path.exists(self.caminho_pdf))

    # ---------------------------------------------------------
    # Testes de Geração de Excel por Seção
    # ---------------------------------------------------------
    def test_gerar_excel_secoes_especificas(self):
        """Testa a geração de Excel para resumo, estoque, devendo e credito."""
        secoes = ['resumo', 'estoque', 'devendo', 'credito']
        for secao in secoes:
            gerar_relatorio_excel_secao(secao, self.contexto, self.caminho_excel, loja_usuario=self.loja1)
            self.assertTrue(os.path.exists(self.caminho_excel))
            wb = openpyxl.load_workbook(self.caminho_excel)
            self.assertIn(wb.active.title, ["Resumo Executivo", "Estoque", "Clientes Devendo", "Clientes com Crédito"])

    def test_gerar_excel_secao_geral(self):
        """Testa a opção 'geral' que cria múltiplas abas consolidadas no Excel."""
        gerar_relatorio_excel_secao('geral', self.contexto, self.caminho_excel, loja_usuario=self.loja1)
        self.assertTrue(os.path.exists(self.caminho_excel))
        
        wb = openpyxl.load_workbook(self.caminho_excel)
        # Deve conter múltiplas planilhas criadas para a exportação geral
        self.assertGreaterEqual(len(wb.sheetnames), 3)

    def test_aliases_funcoes(self):
        """Verifica se os apelidos (aliases) das funções apontam corretamente."""
        gerar_relatorio_pdf('resumo', self.contexto, self.caminho_pdf, loja_usuario=self.loja1)
        gerar_relatorio_excel('resumo', self.contexto, self.caminho_excel, loja_usuario=self.loja1)
        self.assertTrue(os.path.exists(self.caminho_pdf))
        self.assertTrue(os.path.exists(self.caminho_excel))

    def test_gerar_excel_secao_desconhecida_fallback(self):
        """Testa o bloco else (fallback) para uma seção Excel desconhecida."""
        gerar_relatorio_excel_secao('secao_inexistente', self.contexto, self.caminho_excel, loja_usuario=self.loja1)
        self.assertTrue(os.path.exists(self.caminho_excel))
        wb = openpyxl.load_workbook(self.caminho_excel)
        # O fallback padrão cria a aba de Resumo e Estoque
        self.assertGreaterEqual(len(wb.sheetnames), 2)