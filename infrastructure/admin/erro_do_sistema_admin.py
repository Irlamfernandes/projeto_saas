from django.contrib import admin, messages
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display
from infrastructure.models import ErroDoSistema

CAMPOS = ('tipo', 'mensagem', 'local', 'caminho', 'metodo', 'loja', 'usuario', 'ocorrencias', 'primeira_vez', 'ultima_vez')


@admin.register(ErroDoSistema)
class ErroDoSistemaAdmin(ModelAdmin):
    """Erros de produção. Corrigiu? Marque como resolvido: se voltar a acontecer, aparece de novo como novo."""
    list_display = ('ultima_vez', 'situacao', 'tipo', 'local', 'caminho', 'ocorrencias', 'loja')
    list_filter = ('resolvido', 'tipo', 'loja')
    search_fields = ('tipo', 'mensagem', 'local', 'caminho')
    list_select_related = ('loja',)
    date_hierarchy = 'ultima_vez'
    readonly_fields = (*CAMPOS, 'caminho_do_erro')
    fieldsets = (
        (None, {'fields': ('resolvido', 'tipo', 'mensagem', 'local')}),
        ('Onde e quando', {'fields': ('caminho', 'metodo', 'loja', 'usuario', 'ocorrencias', 'primeira_vez', 'ultima_vez')}),
        ('Caminho do erro pelo código', {'fields': ('caminho_do_erro',)}),
    )
    actions = ('marcar_resolvidos', 'reabrir')

    def has_add_permission(self, request):
        return False

    @display(description="Situação", ordering='resolvido', label={'Em aberto': 'danger', 'Resolvido': 'success'})
    def situacao(self, erro):
        return 'Resolvido' if erro.resolvido else 'Em aberto'

    @display(description="Traceback")
    def caminho_do_erro(self, erro):
        return format_html('<pre class="whitespace-pre-wrap text-xs">{}</pre>', erro.detalhes or '—')

    @admin.action(description="Marcar como resolvido")
    def marcar_resolvidos(self, request, queryset):
        quantos = queryset.update(resolvido=True)
        messages.success(request, f"{quantos} erro(s) marcado(s) como resolvido(s).")

    @admin.action(description="Reabrir")
    def reabrir(self, request, queryset):
        quantos = queryset.update(resolvido=False)
        messages.success(request, f"{quantos} erro(s) reaberto(s).")
