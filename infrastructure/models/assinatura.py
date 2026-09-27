import uuid
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from infrastructure.models.loja_model import LojaModel


class UnidadeDeTempo(models.TextChoices):
    DIAS = 'dias', 'Dias'
    MESES = 'meses', 'Meses'


class Plano(models.Model):
    """Opção de renovação. O preço é editável no admin; a cobrança guarda uma cópia do que foi contratado."""
    nome = models.CharField(max_length=50)
    quantidade = models.PositiveSmallIntegerField(help_text="Quanto tempo o plano soma ao vencimento.")
    unidade = models.CharField(max_length=5, choices=UnidadeDeTempo.choices)
    preco = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    ativo = models.BooleanField(default=True, help_text="Desmarque para tirar o plano da tela de renovação.")
    ordem = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = 'planos'
        verbose_name = 'Plano'
        verbose_name_plural = 'Planos'
        ordering = ['ordem', 'pk']

    def __str__(self):
        return self.nome


class StatusDaCobranca(models.TextChoices):
    PENDENTE = 'pendente', 'Aguardando pagamento'
    PAGA = 'paga', 'Paga'
    EXPIRADA = 'expirada', 'Expirada'


class Cobranca(models.Model):
    """Um Pix gerado para renovar o plano. Só vira 'paga' depois de o Mercado Pago confirmar."""
    # Vai ao Mercado Pago como referência e chave de idempotência: única em qualquer banco (teste ou produção).
    referencia = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='cobrancas')
    plano = models.ForeignKey(Plano, on_delete=models.PROTECT, related_name='cobrancas')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    # Cópia do plano no momento da compra: mudar o plano depois não altera o que foi pago.
    plano_nome = models.CharField(max_length=50)
    quantidade = models.PositiveSmallIntegerField()
    unidade = models.CharField(max_length=5, choices=UnidadeDeTempo.choices)
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    email_pagador = models.CharField(max_length=254)

    status = models.CharField(max_length=10, choices=StatusDaCobranca.choices, default=StatusDaCobranca.PENDENTE)
    pagamento_id = models.CharField(max_length=40, blank=True, default='', help_text="ID do pagamento no Mercado Pago.")
    pix_copia_e_cola = models.TextField(blank=True, default='')
    pix_qr_code = models.TextField(blank=True, default='', help_text="Imagem PNG do QR code em base64.")
    criada_em = models.DateTimeField(auto_now_add=True)
    expira_em = models.DateTimeField()
    paga_em = models.DateTimeField(null=True, blank=True)
    vencimento_anterior = models.DateField(null=True, blank=True)
    vencimento_novo = models.DateField(null=True, blank=True)

    class Meta:
        db_table = 'cobrancas'
        verbose_name = 'Cobrança'
        verbose_name_plural = 'Cobranças'
        ordering = ['-criada_em']

    def __str__(self):
        return f"{self.plano_nome} · {self.loja} · {self.get_status_display()}"
