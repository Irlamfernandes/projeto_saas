from decimal import Decimal
from django.db import models
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto

class Venda(models.Model):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='vendas')
    cliente = models.ForeignKey(Cliente, on_delete=models.SET_NULL, null=True, blank=True, related_name='vendas')
    data_venda = models.DateTimeField(auto_now_add=True)
    valor_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    observacoes = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"Venda #{self.id} - {self.cliente.nome} (R$ {self.valor_total})"

class ItemVenda(models.Model):
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT)
    quantidade = models.PositiveIntegerField(default=1)
    preco_unitario = models.DecimalField(max_digits=10, decimal_places=2)

    def subtotal(self):
        return self.quantidade * self.preco_unitario

class PagamentoCliente(models.Model):
    """Pagamento geral ou abatimento feito pelo cliente na caderneta"""
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='pagamentos_cliente')
    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE, related_name='pagamentos')
    valor = models.DecimalField(max_digits=10, decimal_places=2)
    data_pagamento = models.DateTimeField(auto_now_add=True)
    observacao = models.CharField(max_length=255, blank=True, null=True)

    def __str__(self):
        return f"Pagamento - {self.cliente.nome} (R$ {self.valor})"