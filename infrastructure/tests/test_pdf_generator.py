import os
import tempfile
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto
from infrastructure.models.venda import Venda, ItemVenda, PagamentoCliente
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