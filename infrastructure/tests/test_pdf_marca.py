import io
from unittest.mock import patch
from django.test import TestCase
from PIL import Image as ImagemPil
from reportlab.platypus import Image, Paragraph, Spacer, Table
from infrastructure.models import Cliente, LojaModel
from infrastructure.utils.pdf_generator import gerar_extrato_pdf_cliente
from infrastructure.utils.pdf_marca import LADO_DA_MARCA, cabecalho_da_loja, marca_da_loja
from infrastructure.utils.relatorios_export import gerar_relatorio_pdf
from tests.apoio import URL_PUBLICA


def webp(largura, altura):
    buffer = io.BytesIO()
    ImagemPil.new('RGB', (largura, altura), 'green').save(buffer, 'WEBP')
    return buffer.getvalue()


class StorageDeLeitura:
    def __init__(self, conteudo):
        self.conteudo = conteudo
        self.pedidos = []

    def baixar(self, url):
        self.pedidos.append(url)
        return self.conteudo


class MarcaNoPdfTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria <Pão>", logo_url=f"{URL_PUBLICA}/lojas/logo.webp")

    def test_marca_em_webp_e_redimensionada_proporcionalmente(self):
        storage = StorageDeLeitura(webp(400, 200))

        marca = marca_da_loja(self.loja, storage)

        self.assertIsInstance(marca, Image)
        self.assertEqual((marca.drawWidth, marca.drawHeight), (LADO_DA_MARCA, LADO_DA_MARCA / 2))
        self.assertEqual(storage.pedidos, [self.loja.logo_url])

    def test_sem_marca_nao_busca_nada(self):
        self.loja.logo_url = ''
        storage = StorageDeLeitura(webp(10, 10))
        self.assertIsNone(marca_da_loja(self.loja, storage))
        self.assertEqual(storage.pedidos, [])

    def test_marca_indisponivel_ou_ilegivel_nao_impede_o_pdf(self):
        self.assertIsNone(marca_da_loja(self.loja, StorageDeLeitura(None)))
        with self.assertLogs('infrastructure.utils.pdf_marca', 'WARNING'):
            self.assertIsNone(marca_da_loja(self.loja, StorageDeLeitura(b'lixo')))

    def test_cabecalho_com_marca_fica_ao_lado_do_nome(self):
        tabela, espaco = cabecalho_da_loja(self.loja, "Extrato", StorageDeLeitura(webp(10, 10)))
        self.assertIsInstance(tabela, Table)
        self.assertIsInstance(espaco, Spacer)

    def test_cabecalho_sem_marca_tem_nome_escapado_e_subtitulo(self):
        nome, subtitulo = cabecalho_da_loja(self.loja, "Extrato", StorageDeLeitura(None))
        self.assertIsInstance(nome, Paragraph)
        self.assertIn("Padaria &lt;Pão&gt;", nome.text)
        self.assertEqual(subtitulo.text, "Extrato")

    def test_sem_storage_usa_o_do_settings(self):
        with patch('infrastructure.utils.pdf_marca.SupabaseStorage.from_settings') as fabrica:
            fabrica.return_value.baixar.return_value = None
            marca_da_loja(self.loja)
        fabrica.return_value.baixar.assert_called_once_with(self.loja.logo_url)


class PdfsComMarcaTest(TestCase):
    """Os PDFs saem de verdade com a marca em WebP dentro."""

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria", logo_url=f"{URL_PUBLICA}/lojas/logo.webp")
        self.storage = StorageDeLeitura(webp(300, 300))

    def test_extrato(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")
        pdf = io.BytesIO()
        gerar_extrato_pdf_cliente(cliente, pdf, storage=self.storage)
        self.assertTrue(pdf.getvalue().startswith(b'%PDF'))
        self.assertIn(b'/Subtype /Image', pdf.getvalue())

    def test_relatorio(self):
        from infrastructure.tests.test_relatorios_export import _relatorio
        pdf = io.BytesIO()
        gerar_relatorio_pdf('resumo', _relatorio(), pdf, loja=self.loja, storage=self.storage)
        self.assertIn(b'/Subtype /Image', pdf.getvalue())

    def test_relatorio_sem_loja_sai_sem_cabecalho(self):
        from infrastructure.tests.test_relatorios_export import _relatorio
        pdf = io.BytesIO()
        gerar_relatorio_pdf('resumo', _relatorio(), pdf)
        self.assertNotIn(b'/Subtype /Image', pdf.getvalue())
        self.assertEqual(self.storage.pedidos, [])
