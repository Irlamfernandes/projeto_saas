from django.contrib import admin
from unfold.admin import ModelAdmin
from infrastructure.models import TentativasDeLogin


@admin.register(TentativasDeLogin)
class TentativasDeLoginAdmin(ModelAdmin):
    """Quem errou a senha. Para liberar na hora alguém bloqueado, apague o registro (ou espere 15 minutos)."""
    list_display = ('usuario', 'falhas', 'ultima_falha', 'bloqueado_ate')
    search_fields = ('usuario',)
    readonly_fields = ('usuario', 'falhas', 'ultima_falha', 'bloqueado_ate')

    def has_add_permission(self, request):
        return False
