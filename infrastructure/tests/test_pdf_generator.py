from infrastructure.utils.pdf_generator import COR_CREDITO, COR_DEVENDO, COR_NEUTRA, linhas_de_compras, situacao_financeira
from django.utils import timezone
from datetime import date, datetime, timezone as dt_timezone
import io
import os
import tempfile
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto
from infrastructure.models.venda import Venda, ItemVenda, PagamentoCliente, Parcela
from infrastructure.utils.pdf_generator import gerar_extrato_pdf_cliente


class PdfGeneratorTest(TestCase):

    def setUp(self):
        # Lojas
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Matriz", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Filial", ativo=True)

        # Cliente da Loja 1
        self.cliente = Cliente.objects.create(
            loja=self.loja1,
            nome="Maria Souza",
            telefone="24988887777"
        )

        # Produto
        self.produto = Produto.objects.create(
            loja=self.loja1,
            nome="Caderno 10 Matérias",
            preco_venda=Decimal('25.00')
        )

        # Arquivo temporário para salvar os PDFs durante os testes
        self.temp_file = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        self.temp_file.close()
        self.caminho_pdf = self.temp_file.name

    def tearDown(self):
        # Remove o arquivo temporário após cada teste
        if os.path.exists(self.caminho_pdf):
            os.unlink(self.caminho_pdf)

    def test_gerar_extrato_permission_denied(self):
        """Deve lançar PermissionDenied se o usuário pertencer a outra loja."""
        with self.assertRaises(PermissionDenied):
            gerar_extrato_pdf_cliente(self.cliente, self.caminho_pdf, loja_usuario=self.loja2)

    def test_gerar_extrato_pdf_com_saldo_positivo_e_vendas(self):
        """Gera o PDF com saldo positivo (devendo) e lista de compras."""
        # Cria uma venda para gerar saldo devedor
        venda = Venda.objects.create(
            loja=self.loja1,
            cliente=self.cliente,
            valor_total=Decimal('50.00')
        )
        ItemVenda.objects.create(
            venda=venda,
            produto=self.produto,
            quantidade=2,
            preco_unitario=Decimal('25.00')
        )

        # Executa a geração do PDF
        gerar_extrato_pdf_cliente(self.cliente, self.caminho_pdf, loja_usuario=self.loja1)

        # Verifica se o arquivo foi criado e não está vazio
        self.assertTrue(os.path.exists(self.caminho_pdf))
        self.assertGreater(os.path.getsize(self.caminho_pdf), 0)

    def test_gerar_extrato_pdf_com_saldo_negativo(self):
        """Gera o PDF com saldo negativo (crédito a favor do cliente)."""
        # Cria um pagamento maior que as compras para gerar saldo negativo (crédito)
        PagamentoCliente.objects.create(
            loja=self.loja1,
            cliente=self.cliente,
            valor=Decimal('100.00')
        )

        gerar_extrato_pdf_cliente(self.cliente, self.caminho_pdf)

        self.assertTrue(os.path.exists(self.caminho_pdf))
        self.assertGreater(os.path.getsize(self.caminho_pdf), 0)

    def test_gerar_extrato_pdf_sem_vendas_e_saldo_zerado(self):
        """Gera o PDF para um cliente sem compras e saldo zerado."""
        gerar_extrato_pdf_cliente(self.cliente, self.caminho_pdf, loja_usuario=self.loja1)

        self.assertTrue(os.path.exists(self.caminho_pdf))
        self.assertGreater(os.path.getsize(self.caminho_pdf), 0)


    def test_nome_com_marcacao_nao_quebra_o_pdf(self):
        """Regressão: ReportLab interpretava o nome como marcação; 'Ana <b' derrubava a geração (HTTP 500)."""
        for nome in ["Ana <b", "<font size=40>GIGANTE</font>", "Loja & Cia"]:
            with self.subTest(nome=nome):
                self.cliente.nome = nome
                self.loja1.nome_loja = nome
                buffer = io.BytesIO()
                gerar_extrato_pdf_cliente(self.cliente, buffer)
                self.assertTrue(buffer.getvalue().startswith(b"%PDF"))

    def test_datas_das_compras_no_fuso_local(self):
        """Regressão: o horário saía em UTC (3h adiantado em relação a Brasília)."""
        meio_dia_utc = datetime(2026, 1, 10, 12, 0, tzinfo=dt_timezone.utc)
        venda = Venda.objects.create(loja=self.loja1, cliente=self.cliente, valor_total=Decimal('50.00'), data_venda=meio_dia_utc)
        ItemVenda.objects.create(venda=venda, produto=self.produto, quantidade=2, preco_unitario=Decimal('25.00'))

        self.assertEqual(linhas_de_compras(self.cliente), [["10/01/2026 09:00", "2× Caderno 10 Matérias", "R$ 50,00"]])

    def test_compra_com_vencimento_mostra_a_data(self):
        venda = Venda.objects.create(loja=self.loja1, cliente=self.cliente, valor_total=Decimal('50.00'))
        ItemVenda.objects.create(venda=venda, produto=self.produto, quantidade=2, preco_unitario=Decimal('25.00'))
        Parcela.objects.create(venda=venda, vencimento=date(2026, 10, 15))

        self.assertEqual(linhas_de_compras(self.cliente)[0][1], "2× Caderno 10 Matérias · vence 15/10/2026")

    def test_extrato_lista_so_as_cinco_compras_mais_recentes(self):
        for dia in range(1, 8):
            Venda.objects.create(loja=self.loja1, cliente=self.cliente, valor_total=Decimal(dia),
                                 data_venda=timezone.make_aware(datetime(2026, 1, dia, 12, 0)))

        datas = [linha[0][:2] for linha in linhas_de_compras(self.cliente)]
        self.assertEqual(datas, ["07", "06", "05", "04", "03"])

    def test_cliente_sem_compras(self):
        self.assertEqual(linhas_de_compras(self.cliente), [["-", "Nenhuma compra registrada", "-"]])

    def test_situacao_financeira(self):
        self.assertEqual(situacao_financeira(Decimal('10')), ("Situação: DEVENDO R$ 10,00 (Valor Pendente)", COR_DEVENDO))
        self.assertEqual(situacao_financeira(Decimal('-5')), ("Situação: CRÉDITO DE R$ 5,00 (Valor a mais)", COR_CREDITO))
        self.assertEqual(situacao_financeira(Decimal('0'))[1], COR_NEUTRA)
