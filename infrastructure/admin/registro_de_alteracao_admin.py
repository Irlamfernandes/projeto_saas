from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from infrastructure.models import Acao, RegistroDeAlteracao

CORES_DAS_ACOES = {
    Acao.VENDA_CANCELADA: 'danger',
    Acao.PLANO_RENOVADO: 'success',
    Acao.PAGAMENTO_REGISTRADO: 'success',
    Acao.VENDA_EDITADA: 'warning',
    Acao.PRODUTO_EDITADO: 'warning',
    Acao.CLIENTE_EDITADO: 'warning',
}


@admin.register(RegistroDeAlteracao)
class RegistroDeAlteracaoAdmin(ModelAdmin):
    """Só leitura: o histórico não pode ser criado, editado nem apagado à mão."""
    list_display = ('data', 'loja', 'usuario', 'tipo', 'descricao')
    list_filter = ('acao', 'loja', 'data')
    search_fields = ('descricao',)
    list_select_related = ('loja', 'usuario')
    date_hierarchy = 'data'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description="Ação", ordering='acao', label=CORES_DAS_ACOES)
    def tipo(self, registro):
        return registro.acao, registro.get_acao_display()
