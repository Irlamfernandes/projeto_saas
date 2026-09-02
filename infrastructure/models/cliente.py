from decimal import Decimal
from django.db import models
from django.db.models import Sum
from infrastructure.models.loja_model import LojaModel

class Cliente(models.Model):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='clientes')
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    endereco = models.TextField(blank=True, null=True)
    data_criacao = models.DateTimeField(auto_now_add=True)

    @property
    def saldo_geral(self):
        total_compras = self.vendas.aggregate(Sum('valor_total'))['valor_total__sum'] or Decimal('0.00')
        total_pagamentos = self.pagamentos.aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
        return total_compras - total_pagamentos

    def __str__(self):
        return self.nome