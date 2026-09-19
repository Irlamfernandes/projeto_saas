import uuid
from django.db import models
from infrastructure.models.loja_model import LojaModel

class FaturaAssinatura(models.Model):
    STATUS_CHOICES = [
        ('PENDENTE', 'Pendente'),
        ('PAGO', 'Pago'),
        ('CANCELADO', 'Cancelado'),
    ]

    PLANO_CHOICES = [
        ('1_MES', 'Mensal (1 Mês)'),
        ('3_MESES', 'Trimestral (3 Meses)'),
        ('6_MESES', 'Semestral (6 Meses)'),
        ('1_ANO', 'Anual (1 Ano)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='faturas', db_index=True)
    
    plano = models.CharField(max_length=20, choices=PLANO_CHOICES)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDENTE', db_index=True)
    
    qr_code_pix = models.TextField(blank=True, null=True)
    qr_code_imagem_url = models.TextField(blank=True, null=True)
    id_transacao_gateway = models.CharField(max_length=100, blank=True, null=True)
    
    data_criacao = models.DateTimeField(auto_now_add=True, db_index=True)
    data_pagamento = models.DateTimeField(blank=True, null=True)

    class Meta:
        db_table = 'faturas_assinatura'
        verbose_name = 'Fatura de Assinatura'
        verbose_name_plural = 'Faturas de Assinaturas'

    def __str__(self):
        return f"Fatura #{self.pk} - {self.loja.nome_loja} ({self.get_plano_display()}) - {self.status}"