from django.contrib import admin
from django.core.exceptions import PermissionDenied
from infrastructure.models.loja_model import LojaModel

@admin.register(LojaModel)
class LojaAdmin(admin.ModelAdmin):
    list_display = ('id', 'nome_loja', 'ativo', 'vencimento', 'criado_em')
    search_fields = ('nome_loja',)
    list_filter = ('ativo', 'vencimento', 'criado_em')

    def get_readonly_fields(self, request, obj=None):
        # O vencimento só muda por pagamento confirmado; à mão, só o superusuário (casos especiais).
        return () if request.user.is_superuser else ('vencimento',)
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        
        if hasattr(request.user, 'loja') and request.user.loja:
            return qs.filter(pk=request.user.loja.pk)
        
        return qs.none()

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            if hasattr(request.user, 'loja') and request.user.loja:
                if change and obj.pk != request.user.loja.pk:
                    raise PermissionDenied("Acesso negado: Você não tem permissão para alterar esta loja.")
        
        super().save_model(request, obj, form, change)