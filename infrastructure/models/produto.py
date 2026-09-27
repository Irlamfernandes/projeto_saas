from decimal import Decimal
from django.core.validators import MinValueValidator
from django.db import models
from infrastructure.models.loja_model import LojaModel


class Unidade(models.TextChoices):
    """Como o produto é contado e vendido. Peso, volume e comprimento aceitam frações (ex.: 0,350 kg)."""
    UNIDADE = 'un', 'Unidade'
    QUILO = 'kg', 'Quilo (kg)'
    GRAMA = 'g', 'Grama (g)'
    LITRO = 'l', 'Litro (L)'
    MILILITRO = 'ml', 'Mililitro (ml)'
    METRO = 'm', 'Metro (m)'
    CENTIMETRO = 'cm', 'Centímetro (cm)'
    PAR = 'par', 'Par'
    DUZIA = 'dz', 'Dúzia'
    CAIXA = 'cx', 'Caixa'
    PACOTE = 'pct', 'Pacote'


SIGLAS = {
    Unidade.UNIDADE: 'un.', Unidade.QUILO: 'kg', Unidade.GRAMA: 'g', Unidade.LITRO: 'L', Unidade.MILILITRO: 'ml',
    Unidade.METRO: 'm', Unidade.CENTIMETRO: 'cm', Unidade.PAR: 'par', Unidade.DUZIA: 'dz', Unidade.CAIXA: 'cx',
    Unidade.PACOTE: 'pct',
}
# Casas decimais aceitas na quantidade; as unidades que não estão aqui só aceitam números inteiros.
CASAS_DECIMAIS = {Unidade.QUILO: 3, Unidade.LITRO: 3, Unidade.METRO: 2}
QUANTIDADE_MAXIMA_DE_CASAS = 3
MILESIMO = Decimal('0.001')
MAXIMO_DE_OPCOES = 5


def sigla(unidade):
    return SIGLAS.get(unidade, unidade)


def casas_decimais(unidade):
    return CASAS_DECIMAIS.get(unidade, 0)


def quantidade_aceita(quantidade, unidade):
    """A quantidade cabe nas casas decimais da unidade? (2,5 kg sim; 2,5 unidades não.)"""
    quantidade = Decimal(quantidade)
    return quantidade == quantidade.quantize(Decimal(1).scaleb(-casas_decimais(unidade)))


def campo_de_quantidade(**kwargs):
    return models.DecimalField(max_digits=12, decimal_places=QUANTIDADE_MAXIMA_DE_CASAS, **kwargs)


class Produto(models.Model):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='produtos')
    codigo_interno = models.CharField(max_length=50, blank=True, default='', db_index=True)
    
    nome = models.CharField(max_length=150, db_index=True)
    categoria = models.CharField(max_length=100, blank=True, default='', db_index=True)
    descricao = models.TextField(blank=True, default='')
    
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
    
    unidade = models.CharField(max_length=5, choices=Unidade.choices, default=Unidade.UNIDADE)
    # Sem controle (ex.: feito na hora, serviço, sob encomenda): vende sem conferir nem baixar o estoque.
    controla_estoque = models.BooleanField(default=True)
    quantidade_estoque = campo_de_quantidade(
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]
    )
    # Escolhas feitas na venda, com nome e valores dados pela loja (ex.: Tamanho P/M/G, Sabor, Cor):
    # [{'nome': 'Tamanho', 'valores': [{'nome': 'G', 'acrescimo': '5.00'}, ...]}, ...]. Não mexem no estoque.
    opcoes = models.JSONField(default=list, blank=True)

    data_criacao = models.DateTimeField(auto_now_add=True)

    @property
    def sigla(self):
        return sigla(self.unidade)

    @property
    def casas_decimais(self):
        return casas_decimais(self.unidade)

    def __str__(self):
        codigo_str = f"[{self.codigo_interno}] " if self.codigo_interno else ""
        return f"{codigo_str}{self.nome} - R$ {self.preco_venda}"

    class Meta:
        db_table = 'produtos'
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        indexes = [
            models.Index(fields=['loja', '-data_criacao'], name='produto_loja_criacao_idx'),
            # Estoque baixo (dashboard) e inventário ordenado (relatório).
            models.Index(fields=['loja', 'quantidade_estoque'], name='produto_loja_estoque_idx'),
        ]


class ProdutoImagem(models.Model):
    produto = models.ForeignKey(
        Produto, 
        on_delete=models.CASCADE, 
        related_name='imagens'
    )
    imagem_url = models.URLField(max_length=500)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Imagem de {self.produto.nome}"

    class Meta:
        db_table = 'produto_imagens'
        verbose_name = 'Imagem do Produto'
        verbose_name_plural = 'Imagens dos Produtos'