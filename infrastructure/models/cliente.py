from decimal import Decimal
from django.apps import apps
from django.db import models
from django.db.models import DecimalField, OuterRef, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from infrastructure.models.loja_model import LojaModel

_DINHEIRO = DecimalField(max_digits=12, decimal_places=2)


def _total_por_cliente(nome_modelo, campo):
    """Subquery com a soma de `campo` dos registros do cliente na mesma loja (0 se não houver)."""
    modelo = apps.get_model('infrastructure', nome_modelo)
    soma = (
        modelo.objects.filter(cliente=OuterRef('pk'), loja=OuterRef('loja'))
        .order_by()
        .values('cliente')
        .annotate(total=Sum(campo))
        .values('total')
    )
    return Coalesce(Subquery(soma, output_field=_DINHEIRO), Value(Decimal('0.00')), output_field=_DINHEIRO)


class ClienteQuerySet(models.QuerySet):

    def com_saldo(self):
        """Anota `saldo_calculado` (compras − pagamentos) na mesma consulta, evitando N+1."""
        return self.annotate(
            saldo_calculado=_total_por_cliente('Venda', 'valor_total') - _total_por_cliente('PagamentoCliente', 'valor')
        )


class Cliente(models.Model):
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='clientes')
    nome = models.CharField(max_length=255)
    telefone = models.CharField(max_length=20, blank=True, default='')
    email = models.EmailField(blank=True, default='')
    endereco = models.TextField(blank=True, default='')
    data_criacao = models.DateTimeField(auto_now_add=True)

    objects = ClienteQuerySet.as_manager()

    class Meta:
        indexes = [
            # Select de clientes (ordem alfabética) e listagem (mais recentes primeiro).
            models.Index(fields=['loja', 'nome'], name='cliente_loja_nome_idx'),
            models.Index(fields=['loja', '-data_criacao'], name='cliente_loja_criacao_idx'),
        ]

    @property
    def saldo_geral(self):
        """Positivo: cliente devendo. Negativo: cliente com crédito."""
        if hasattr(self, 'saldo_calculado'):
            return self.saldo_calculado
        return Cliente.objects.com_saldo().values_list('saldo_calculado', flat=True).get(pk=self.pk)

    def __str__(self):
        return self.nome
