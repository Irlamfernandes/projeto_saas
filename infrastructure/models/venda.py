from decimal import ROUND_HALF_UP, Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.cliente import Cliente
from infrastructure.models.produto import Produto, campo_de_quantidade
from infrastructure.utils.formatacao import com_opcoes

def subtotal(quantidade, preco):
    """Quantidade × preço, em centavos (0,350 kg × R$ 39,90 = R$ 13,97)."""
    return (quantidade * preco).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


class FormaDePagamento(models.TextChoices):
    DINHEIRO = 'dinheiro', 'Dinheiro'
    PIX = 'pix', 'Pix'
    DEBITO = 'debito', 'Cartão de débito'
    CREDITO = 'credito', 'Cartão de crédito'
    OUTRO = 'outro', 'Outro'


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
    # Como foi pago o que se pagou na hora (venda de balcão: o total; com cliente: o "pago agora").
    forma_pagamento = models.CharField(max_length=10, choices=FormaDePagamento.choices, blank=True, default='')

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
    quantidade = campo_de_quantidade(
        default=Decimal('1'),
        validators=[MinValueValidator(Decimal('0.001'))]
    )
    preco_unitario = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    # Preço de custo do produto no dia da venda: o lucro do mês não muda quando o custo muda depois.
    custo_unitario = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    # O que foi escolhido nas opções do produto: [{'nome': 'Tamanho', 'valor': 'G'}, ...]. O acréscimo já está no preço.
    opcoes = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = 'itens_venda'
        verbose_name = 'Item da Venda'
        verbose_name_plural = 'Itens das Vendas'
        ordering = ['pk']  # ordem em que foram lançados (sem isso o Postgres devolve em qualquer ordem)

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
        return subtotal(self.quantidade, self.preco_unitario)

    @property
    def nome(self):
        """'Camiseta (G, Azul)'; sem opções, só o nome do produto."""
        return com_opcoes(self.produto.nome, self.opcoes)

    def __str__(self):
        return f"{self.quantidade}x {self.produto.nome} (Venda #{self.venda_id})"  # produto é obrigatório (PROTECT)


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
    forma_pagamento = models.CharField(max_length=10, choices=FormaDePagamento.choices, blank=True, default='')
    # Preenchido quando o pagamento foi feito no ato de uma venda: acompanha a venda se ela mudar de cliente.
    venda = models.ForeignKey(
        Venda, on_delete=models.CASCADE, null=True, blank=True, related_name='pagamentos_no_ato',
    )

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
        return f"Pagamento - {self.cliente.nome} (R$ {self.valor})"  # cliente é obrigatório

class Parcela(models.Model):
    """Data combinada para pagar a parte da venda que ficou na caderneta. Venda a prazo sem data = sem parcela.

    O valor de cada parcela não é guardado: é o que ficou a prazo dividido entre elas (sempre em dia se a venda mudar).
    """
    venda = models.ForeignKey(Venda, on_delete=models.CASCADE, related_name='parcelas')
    vencimento = models.DateField(db_index=True)

    class Meta:
        db_table = 'parcelas_venda'
        verbose_name = 'Parcela'
        verbose_name_plural = 'Parcelas'
        ordering = ['vencimento', 'pk']

    def __str__(self):
        return f"Venda #{self.venda_id} · vence {self.vencimento:%d/%m/%Y}"
