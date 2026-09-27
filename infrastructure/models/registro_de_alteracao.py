from django.conf import settings
from django.db import models
from infrastructure.models.loja_model import LojaModel


class Acao(models.TextChoices):
    VENDA_REGISTRADA = 'venda_registrada', 'Venda registrada'
    VENDA_EDITADA = 'venda_editada', 'Venda editada'
    VENDA_CANCELADA = 'venda_cancelada', 'Venda cancelada'
    PAGAMENTO_REGISTRADO = 'pagamento_registrado', 'Pagamento registrado'
    PRODUTO_CADASTRADO = 'produto_cadastrado', 'Produto cadastrado'
    PRODUTO_EDITADO = 'produto_editado', 'Produto editado'
    CLIENTE_CADASTRADO = 'cliente_cadastrado', 'Cliente cadastrado'
    CLIENTE_EDITADO = 'cliente_editado', 'Cliente editado'
    MARCA_ALTERADA = 'marca_alterada', 'Marca da loja alterada'
    PLANO_RENOVADO = 'plano_renovado', 'Plano renovado'
    LEMBRETE_ENVIADO = 'lembrete_enviado', 'Lembrete de pagamento enviado'
    COMPRA_REGISTRADA = 'compra_registrada', 'Compra registrada'
    COMPRA_EXCLUIDA = 'compra_excluida', 'Compra excluída'
    DESPESA_REGISTRADA = 'despesa_registrada', 'Despesa registrada'
    DESPESA_EXCLUIDA = 'despesa_excluida', 'Despesa excluída'
    PERDA_REGISTRADA = 'perda_registrada', 'Perda registrada'
    PERDA_EXCLUIDA = 'perda_excluida', 'Perda excluída'


class RegistroDeAlteracao(models.Model):
    """Quem fez o quê e quando. Só é criado, nunca editado: é o histórico para tirar dúvidas."""
    loja = models.ForeignKey(LojaModel, on_delete=models.CASCADE, related_name='registros_de_alteracao')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    data = models.DateTimeField(auto_now_add=True)
    acao = models.CharField(max_length=30, choices=Acao.choices)
    descricao = models.CharField(max_length=255)
    # Ex.: {"alteracoes": {"preco_venda": ["10.00", "12.00"]}} ou a cópia da venda cancelada.
    detalhes = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'registros_de_alteracao'
        verbose_name = 'Registro de alteração'
        verbose_name_plural = 'Registros de alterações'
        ordering = ['-data']
        indexes = [models.Index(fields=['loja', '-data'], name='registro_loja_data_idx')]

    def __str__(self):
        return f"{self.get_acao_display()}: {self.descricao}"
