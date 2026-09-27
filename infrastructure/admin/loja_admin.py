from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count, URLField
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import display
from infrastructure.models.loja_model import LojaModel

DIAS_PARA_AVISAR = 7


@admin.register(LojaModel)
class LojaAdmin(ModelAdmin):
    list_display = ('marca', 'nome_loja', 'situacao_do_plano', 'vencimento', 'usuarios', 'ativo', 'criado_em')
    list_display_links = ('marca', 'nome_loja')
    search_fields = ('nome_loja',)
    list_filter = ('ativo', 'vencimento', 'criado_em')
    fieldsets = (
        ("Loja", {'fields': ('nome_loja', 'ativo')}),
        ("Plano", {'fields': ('vencimento', 'email_cobranca'),
                   'description': "O vencimento muda sozinho quando um pagamento é confirmado."}),
        ("Marca", {'fields': ('logo_url',), 'description': "A própria loja envia a marca em Configurações."}),
    )

    def get_queryset(self, request):
        qs = super().get_queryset(request).annotate(total_de_usuarios=Count('usuarios'))
        if request.user.is_superuser:
            return qs

        if hasattr(request.user, 'loja') and request.user.loja:
            return qs.filter(pk=request.user.loja.pk)

        return qs.none()

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        if isinstance(db_field, URLField):
            kwargs['assume_scheme'] = 'https'  # endereço sem esquema vira https (padrão do Django 6)
        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_readonly_fields(self, request, obj=None):
        # O vencimento só muda por pagamento confirmado; à mão, só o superusuário (casos especiais).
        return () if request.user.is_superuser else ('vencimento',)

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

    @display(description="Marca", image=True)
    def marca(self, loja):
        return loja.logo_url or None

    @display(description="Plano", label={'em_dia': 'success', 'vencendo': 'warning', 'vencido': 'danger', 'inativa': None})
    def situacao_do_plano(self, loja):
        if not loja.ativo:
            return 'inativa', "Fora do ar"
        dias = (loja.vencimento - timezone.localdate()).days
        if dias < 0:
            return 'vencido', "Vencido"
        if dias <= DIAS_PARA_AVISAR:
            return 'vencendo', "Vence em breve"
        return 'em_dia', "Em dia"

    @display(description="Usuários", ordering='total_de_usuarios')
    def usuarios(self, loja):
        return getattr(loja, 'total_de_usuarios', loja.usuarios.count())
