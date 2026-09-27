import io
from decimal import Decimal
from types import SimpleNamespace
import openpyxl
from django.test import SimpleTestCase
from application.relatorios.selectors import Relatorio
from infrastructure.utils.relatorios_export import (
    FORMATO_MOEDA_EXCEL, SECOES_POR_TIPO, TIPOS_DE_RELATORIO, _texto_pdf, gerar_relatorio_excel, gerar_relatorio_pdf,
)


def _relatorio(**campos):
    base = dict(
        total_geral_vendas=Decimal('1000.00'), ticket_medio=Decimal('50.00'),
        vendas_hoje_valor=Decimal('10.00'), vendas_semana_valor=Decimal('70.00'),
        vendas_mes_valor=Decimal('300.00'), vendas_ano_valor=Decimal('900.00'),
        clientes_devendo=[SimpleNamespace(nome="Ana", saldo_calculado=Decimal('120.50'))],
        total_fiado_pendente=Decimal('120.50'),
        clientes_credito=[SimpleNamespace(nome="Bia", valor_credito=Decimal('20.00'))],
        total_credito_clientes=Decimal('20.00'),
        estoque_ordenado=[SimpleNamespace(nome="Arroz", preco_venda=Decimal('25.90'), quantidade_estoque=Decimal('3.000'), unidade='un'),
                          SimpleNamespace(nome="Queijo", preco_venda=Decimal('39.90'), quantidade_estoque=Decimal('2.500'), unidade='kg')],
    )
    return Relatorio(**{**base, **campos})


def _abrir_excel(tipo, relatorio=None):
    arquivo = io.BytesIO()
    gerar_relatorio_excel(tipo, relatorio or _relatorio(), arquivo)
    arquivo.seek(0)
    return openpyxl.load_workbook(arquivo)


class ExportacaoPdfTest(SimpleTestCase):

    def test_gera_pdf_para_todos_os_tipos(self):
        for tipo in TIPOS_DE_RELATORIO:
            with self.subTest(tipo=tipo):
                arquivo = io.BytesIO()
                gerar_relatorio_pdf(tipo, _relatorio(), arquivo)
                self.assertTrue(arquivo.getvalue().startswith(b"%PDF"))

    def test_gera_pdf_sem_dados(self):
        arquivo = io.BytesIO()
        gerar_relatorio_pdf('geral', _relatorio(clientes_devendo=[], clientes_credito=[], estoque_ordenado=[]), arquivo)
        self.assertTrue(arquivo.getvalue().startswith(b"%PDF"))

    def test_formatacao_dos_valores(self):
        self.assertEqual(_texto_pdf(Decimal('10.5')), "R$ 10,50")
        self.assertEqual(_texto_pdf(Decimal('1234.5')), "R$ 1.234,50")  # regressão: saía "R$ 1234.50"
        self.assertEqual(_texto_pdf(3), "3")
        self.assertEqual(_texto_pdf(2.5), "2,5")
        self.assertEqual(_texto_pdf("Arroz"), "Arroz")


class ExportacaoExcelTest(SimpleTestCase):

    def test_abas_por_tipo(self):
        esperado = {
            'resumo': ["Resumo Executivo"],
            'temporal': ["Desempenho Temporal"],
            'devendo': ["Clientes Devendo"],
            'credito': ["Clientes com Crédito"],
            'estoque': ["Estoque"],
            'geral': ["Resumo Executivo", "Desempenho Temporal", "Clientes Devendo", "Clientes com Crédito", "Estoque"],
        }
        self.assertEqual(set(esperado), TIPOS_DE_RELATORIO)
        for tipo, abas in esperado.items():
            with self.subTest(tipo=tipo):
                self.assertEqual(_abrir_excel(tipo).sheetnames, abas)

    def test_excel_temporal_traz_os_periodos(self):
        """Regressão: o Excel 'temporal' caía no fallback e vinha sem os dados de período."""
        linhas = list(_abrir_excel('temporal').active.values)
        self.assertEqual(linhas, [
            ("Período", "Faturamento"), ("Hoje", 10), ("Últimos 7 dias", 70), ("Este Mês", 300), ("Este Ano", 900),
        ])

    def test_valores_monetarios_sao_numeros_formatados(self):
        aba = _abrir_excel('estoque').active
        self.assertEqual([c.value for c in aba[2]], ["Arroz", 25.9, 3, "un."])
        self.assertEqual([c.value for c in aba[3]], ["Queijo", 39.9, 2.5, "kg"])
        self.assertEqual(aba['B2'].number_format, FORMATO_MOEDA_EXCEL)
        self.assertEqual(aba['C2'].data_type, 'n')

    def test_credito_e_exportado_como_valor_positivo(self):
        self.assertEqual(list(_abrir_excel('credito').active.values)[1], ("Bia", 20))

    def test_nome_de_cliente_nunca_vira_formula(self):
        """Regressão: '=HYPERLINK(...)' no nome do cliente virava fórmula ativa na planilha."""
        for nome in ['=HYPERLINK("http://x","clique")', '+1+1', '-2+3', '@SUM(A1)']:
            with self.subTest(nome=nome):
                devedor = SimpleNamespace(nome=nome, saldo_calculado=Decimal('1.00'))
                celula = _abrir_excel('devendo', _relatorio(clientes_devendo=[devedor])).active['A2']
                self.assertEqual((celula.data_type, celula.value), ('s', nome))

    def test_geral_e_a_uniao_das_secoes(self):
        secoes_individuais = [SECOES_POR_TIPO[t][0] for t in ('resumo', 'temporal', 'devendo', 'credito', 'estoque')]
        self.assertEqual(list(SECOES_POR_TIPO['geral']), secoes_individuais)


class RodapeDoRelatorioPdfTest(SimpleTestCase):

    def _documento(self):
        from types import SimpleNamespace
        return SimpleNamespace(leftMargin=30, rightMargin=30, pagesize=(612, 792), page=2)

    def test_data_pagina_e_assinatura(self):
        from datetime import datetime
        from unittest.mock import MagicMock
        from infrastructure.utils.relatorios_export import _rodape_da_pagina
        canvas = MagicMock()
        _rodape_da_pagina(canvas, self._documento(), gerado_em=datetime(2026, 9, 27, 14, 5), assinatura="Sistema CorsariosCode")
        canvas.drawString.assert_called_once_with(30, 20, "Gerado em 27/09/2026 às 14:05 · Página 2")
        canvas.drawRightString.assert_called_once_with(582, 20, "Sistema CorsariosCode")

    def test_sem_assinatura_so_data_e_pagina(self):
        from datetime import datetime
        from unittest.mock import MagicMock
        from infrastructure.utils.relatorios_export import _rodape_da_pagina
        canvas = MagicMock()
        _rodape_da_pagina(canvas, self._documento(), gerado_em=datetime(2026, 9, 27), assinatura='')
        canvas.drawRightString.assert_not_called()

    def test_pdf_sai_com_o_rodape(self):
        arquivo = io.BytesIO()
        gerar_relatorio_pdf('geral', _relatorio(), arquivo, assinatura="Sistema CorsariosCode")
        self.assertTrue(arquivo.getvalue().startswith(b'%PDF'))
