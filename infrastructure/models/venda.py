from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto

class Venda(models.Model):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='vendas', db_index=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='vendas', db_index=True)
    data_venda = models.DateTimeField(default=timezone.now, db_index=True)
    data_atualizacao = models.DateTimeField(auto_now=True, db_index=True)
    valor_total = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    observacoes = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'vendas'
        verbose_name = 'Venda'
        verbose_name_plural = 'Vendas'
        indexes = [
            # Listagem da loja (mais recentes primeiro) e somas do dashboard por período.
            models.Index(fields=['loja', '-data_venda'], name='venda_loja_data_idx'),
        ]

    def clean(self):
        super().clean()
        if self.cliente and self.cliente.loja != self.loja:
            raise ValidationError({
                'cliente': 'O cliente selecionado não pertence à mesma loja desta venda.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        cliente_nome = self.cliente.nome if self.cliente else 'Cliente Não Identificado'
        return f"Venda #{self.pk or 'Nova'} - {cliente_nome} (R$ {self.valor_total})"


class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens', db_index=True)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, db_index=True)
    quantidade = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)]
    )
    preco_unitario = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )

    class Meta:
        db_table = 'itens_venda'
        verbose_name = 'Item da Venda'
        verbose_name_plural = 'Itens das Vendas'

    def clean(self):
        super().clean()
        if self.produto and self.venda and self.produto.loja != self.venda.loja:
            raise ValidationError({
                'produto': 'O produto selecionado não pertence à mesma loja desta venda.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def subtotal(self):
        return self.quantidade * self.preco_unitario

    def __str__(self):
        produto_nome = self.produto.nome if self.produto else 'Produto Removido'
        return f"{self.quantidade}x {produto_nome} (Venda #{self.venda_id})"


class PagamentoCliente(models.Model):
    """Pagamento geral ou abatimento feito pelo cliente na caderneta"""
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='pagamentos_cliente', db_index=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='pagamentos', db_index=True)
    valor = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    data_pagamento = models.DateTimeField(auto_now_add=True, db_index=True)
    observacao = models.CharField(max_length=255, blank=True, default='')

    class Meta:
        db_table = 'pagamentos_cliente'
        verbose_name = 'Pagamento de Cliente'
        verbose_name_plural = 'Pagamentos de Clientes'

    def clean(self):
        super().clean()
        if self.cliente and self.cliente.loja != self.loja:
            raise ValidationError({
                'cliente': 'O cliente selecionado não pertence a esta loja.'
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        cliente_nome = self.cliente.nome if self.cliente else 'Cliente Não Identificado'
        return f"Pagamento - {cliente_nome} (R$ {self.valor})"