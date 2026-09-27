from django.contrib import admin
from infrastructure.models import RegistroDeAlteracao


@admin.register(RegistroDeAlteracao)
class RegistroDeAlteracaoAdmin(admin.ModelAdmin):
    """Só leitura: o histórico não pode ser criado, editado nem apagado à mão."""
    list_display = ('data', 'loja', 'usuario', 'acao', 'descricao')
    list_filter = ('acao', 'loja')
    search_fields = ('descricao',)
    list_select_related = ('loja', 'usuario')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
