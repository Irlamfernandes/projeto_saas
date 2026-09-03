from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from infrastructure.models.loja_model import LojaModel

class Produto(models.Model):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='produtos')
    
    nome = models.CharField(max_length=150, db_index=True)
    categoria = models.CharField(max_length=100, blank=True, null=True, db_index=True)
    descricao = models.TextField(blank=True, null=True)
    
    preco_custo = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    preco_venda = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    margem_lucro = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    quantidade_estoque = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0)]
    )
    
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.nome} - R$ {self.preco_venda}"

    class Meta:
        db_table = 'produtos'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'