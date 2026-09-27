"""O que sai da loja: compras de mercadoria (entram no estoque), despesas (aluguel, luz...) e perdas (estoque que se foi)."""
from decimal import Decimal
from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.produto import Produto, campo_de_quantidade
from infrastructure.utils.formatacao import item

MINIMO = [MinValueValidator(Decimal('0.001'))]


def _dinheiro(**kwargs):
    return models.DecimalField(max_digits=12, decimal_places=2, **kwargs)


class Compra(models.Model):
    """Mercadoria comprada para revender: soma no estoque e pode atualizar o preço de custo."""
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='compras')
    data = models.DateField(default=timezone.localdate)
    fornecedor = models.CharField(max_length=120, blank=True, default='')
    observacao = models.CharField(max_length=255, blank=True, default='')
    valor_total = _dinheiro(default=Decimal('0.00'))
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'compras'
        verbose_name = 'Compra'
        verbose_name_plural = 'Compras'
        ordering = ['-data', '-pk']
        indexes = [models.Index(fields=['loja', '-data'], name='compra_loja_data_idx')]

    def __str__(self):
        return f"Compra #{self.pk} · {self.data:%d/%m/%Y}"


class ItemCompra(models.Model):
    compra = models.ForeignKey(Compra, on_delete=models.CASCADE, related_name='itens')
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='itens_de_compra')
    quantidade = campo_de_quantidade(validators=MINIMO)
    custo_unitario = _dinheiro(validators=[MinValueValidator(Decimal('0'))])

    class Meta:
        db_table = 'itens_compra'
        verbose_name = 'Item da compra'
        verbose_name_plural = 'Itens das compras'

    def __str__(self):
        return item(self.quantidade, self.produto.unidade, self.produto.nome)


class Despesa(models.Model):
    """Gasto que não vira estoque: aluguel, luz, embalagem, transporte... A categoria é livre."""
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='despesas')
    data = models.DateField(default=timezone.localdate)
    categoria = models.CharField(max_length=60)
    descricao = models.CharField(max_length=255, blank=True, default='')
    valor = _dinheiro(validators=[MinValueValidator(Decimal('0.01'))])
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'despesas'
        verbose_name = 'Despesa'
        verbose_name_plural = 'Despesas'
        ordering = ['-data', '-pk']
        indexes = [models.Index(fields=['loja', '-data'], name='despesa_loja_data_idx')]

    def __str__(self):
        return f"{self.categoria} · {self.data:%d/%m/%Y}"


class Perda(models.Model):
    """Estoque que saiu sem venda (venceu, quebrou, consumo próprio). Vale pelo custo do produto na época."""
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='perdas')
    data = models.DateField(default=timezone.localdate)
    produto = models.ForeignKey(Produto, on_delete=models.PROTECT, related_name='perdas')
    quantidade = campo_de_quantidade(validators=MINIMO)
    custo_unitario = _dinheiro(default=Decimal('0.00'))
    motivo = models.CharField(max_length=120)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = 'perdas'
        verbose_name = 'Perda'
        verbose_name_plural = 'Perdas'
        ordering = ['-data', '-pk']
        indexes = [models.Index(fields=['loja', '-data'], name='perda_loja_data_idx')]

    @property
    def valor(self):
        return (self.quantidade * self.custo_unitario).quantize(Decimal('0.01'))

    def __str__(self):
        return f"Perda de {self.produto.nome} · {self.data:%d/%m/%Y}"
