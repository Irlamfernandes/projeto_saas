"""Retrato do extrato em PDF e do cabeçalho da loja: textos, fontes, cores, espaços, tabelas e margens."""
from datetime import date, datetime
from decimal import Decimal
from django.core.exceptions import PermissionDenied
from django.test import TestCase
from django.utils import timezone
from infrastructure.models import Cliente, ItemVenda, LojaModel, PagamentoCliente, Parcela, Produto, Venda
from infrastructure.tests.test_pdf_marca import StorageDeLeitura, webp
from infrastructure.utils import pdf_generator
from infrastructure.utils.pdf_generator import gerar_extrato_pdf_cliente, situacao_financeira
from infrastructure.utils.pdf_marca import marca_da_loja
from tests.retrato_pdf import capturando_documento, conferir


class ExtratoRetratoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Padaria Sol")
        self.pao = Produto.objects.create(loja=self.loja, nome="Pão", preco_venda=Decimal('1.00'))

    def venda(self, cliente, dia, parcelas=()):
        venda = Venda.objects.create(loja=self.loja, cliente=cliente, valor_total=Decimal('2.00'),
                                     data_venda=timezone.make_aware(datetime(2026, 3, dia, 9, 30)))
        ItemVenda.objects.create(venda=venda, produto=self.pao, quantidade=2, preco_unitario=Decimal('1.00'))
        for vencimento in parcelas:
            Parcela.objects.create(venda=venda, vencimento=vencimento)
        return venda

    def extrato(self, cliente, storage=None):
        with capturando_documento(pdf_generator) as pdf:
            gerar_extrato_pdf_cliente(cliente, 'extrato.pdf', self.loja, storage)
        return pdf

    def test_cliente_devendo_com_seis_compras(self):
        ana = Cliente.objects.create(loja=self.loja, nome="Ana", telefone="24 99999-0000")
        for dia in range(1, 7):
            venda = self.venda(ana, dia, parcelas={6: [date(2026, 4, 1), date(2026, 5, 1)], 5: [date(2026, 4, 2)]}.get(dia, ()))
        cafe = Produto.objects.create(loja=self.loja, nome="Café", preco_venda=Decimal('1.00'))
        ItemVenda.objects.create(venda=venda, produto=cafe, quantidade=1, preco_unitario=Decimal('1.00'))  # dois itens
        conferir(self, 'extrato_devendo', self.extrato(ana))

    def test_cliente_com_credito_sem_telefone_e_loja_com_marca(self):
        self.loja.logo_url = 'https://exemplo/logo.webp'
        self.loja.save()
        bia = Cliente.objects.create(loja=self.loja, nome="Bia")
        PagamentoCliente.objects.create(loja=self.loja, cliente=bia, valor=Decimal('5.00'))
        conferir(self, 'extrato_credito_com_marca', self.extrato(bia, StorageDeLeitura(webp(96, 48))))

    def test_conta_zerada(self):
        conferir(self, 'extrato_zerado', self.extrato(Cliente.objects.create(loja=self.loja, nome="Caio")))

    def test_cinquenta_centavos_ainda_e_divida(self):
        self.assertEqual(situacao_financeira(Decimal('0.50'))[0], "Situação: DEVENDO R$ 0,50 (Valor Pendente)")

    def test_cliente_de_outra_loja(self):
        de_fora = Cliente.objects.create(loja=LojaModel.objects.create(nome_loja="Outra"), nome="Davi")
        with self.assertRaises(PermissionDenied) as erro:
            gerar_extrato_pdf_cliente(de_fora, 'extrato.pdf', self.loja)
        self.assertEqual(str(erro.exception), "Acesso negado: Este cliente pertence a outra loja.")

    def test_marca_ilegivel_vai_para_o_log_com_o_erro(self):
        self.loja.logo_url = 'https://exemplo/logo.webp'
        with self.assertLogs('infrastructure.utils.pdf_marca', 'WARNING') as log:
            self.assertIsNone(marca_da_loja(self.loja, StorageDeLeitura(b'nao e imagem')))
        self.assertEqual(log.records[0].getMessage(), f"Marca da loja {self.loja.pk} ilegível para o PDF")
        self.assertIsNotNone(log.records[0].exc_info[0])
