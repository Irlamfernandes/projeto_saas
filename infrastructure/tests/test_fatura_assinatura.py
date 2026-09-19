import uuid
from decimal import Decimal
from django.test import TestCase
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.fatura_assinatura import FaturaAssinatura


class FaturaAssinaturaModelTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(
            nome_loja="Loja Assinante"
        )
        self.fatura = FaturaAssinatura.objects.create(
            loja=self.loja,
            plano='1_MES',
            valor=Decimal('49.90'),
            status='PENDENTE',
            id_transacao_gateway='tx_123456',
            qr_code_pix='00020126580014br.gov.bcb.pix...',
            qr_code_imagem_url='https://api.gateway.com/qrcode.png'
        )

    def test_fatura_creation(self):
        """Verifica se os campos da fatura são salvos e gerados corretamente."""
        self.assertIsInstance(self.fatura.id, uuid.UUID)
        self.assertEqual(self.fatura.loja, self.loja)
        self.assertEqual(self.fatura.plano, '1_MES')
        self.assertEqual(self.fatura.valor, Decimal('49.90'))
        self.assertEqual(self.fatura.status, 'PENDENTE')
        self.assertEqual(self.fatura.id_transacao_gateway, 'tx_123456')
        self.assertEqual(self.fatura.qr_code_pix, '00020126580014br.gov.bcb.pix...')
        self.assertEqual(self.fatura.qr_code_imagem_url, 'https://api.gateway.com/qrcode.png')
        self.assertIsNotNone(self.fatura.data_criacao)
        self.assertIsNone(self.fatura.data_pagamento)

    def test_fatura_str(self):
        """O método __str__ deve retornar a formatação esperada da fatura."""
        str_esperada = f"Fatura #{self.fatura.pk} - {self.loja.nome_loja} (Mensal (1 Mês)) - PENDENTE"
        self.assertEqual(str(self.fatura), str_esperada)

    def test_fatura_meta_options(self):
        """Verifica as configurações de Meta do modelo."""
        self.assertEqual(FaturaAssinatura._meta.db_table, 'faturas_assinatura')
        self.assertEqual(str(FaturaAssinatura._meta.verbose_name), 'Fatura de Assinatura')
        self.assertEqual(str(FaturaAssinatura._meta.verbose_name_plural), 'Faturas de Assinaturas')

    def test_fatura_default_status(self):
        """O status padrão da fatura deve ser PENDENTE caso não informado."""
        fatura_padrao = FaturaAssinatura.objects.create(
            loja=self.loja,
            plano='3_MESES',
            valor=Decimal('130.00')
        )
        self.assertEqual(fatura_padrao.status, 'PENDENTE')