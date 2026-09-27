from django.contrib import admin
from unfold.admin import ModelAdmin
from unfold.decorators import display
from infrastructure.models import Cobranca, Plano, StatusDaCobranca
from infrastructure.utils.formatacao import reais

CORES_DO_STATUS = {
    StatusDaCobranca.PAGA: 'success',
    StatusDaCobranca.PENDENTE: 'info',
    StatusDaCobranca.EXPIRADA: None,
}


@admin.register(Plano)
class PlanoAdmin(ModelAdmin):
    """Preços e planos à venda. Só o superusuário mexe (as permissões padrão do Django cuidam disso)."""
    list_display = ('nome', 'duracao', 'preco', 'ativo', 'ordem')
    list_editable = ('preco', 'ativo', 'ordem')
    fieldsets = (
        ("Plano", {'fields': ('nome', ('quantidade', 'unidade'), 'preco')}),
        ("Exibição", {'fields': ('ativo', 'ordem'),
                      'description': "Plano desativado some da tela de renovação; a ordem define a posição."}),
    )

    @display(description="Soma ao vencimento")
    def duracao(self, plano):
        return f"{plano.quantidade} {plano.get_unidade_display().lower()}"


@admin.register(Cobranca)
class CobrancaAdmin(ModelAdmin):
    """Só leitura: uma cobrança só muda pela confirmação do Mercado Pago."""
    list_display = ('criada_em', 'loja', 'plano_nome', 'valor_em_reais', 'situacao', 'vencimento_novo')
    list_filter = ('status', 'loja', 'criada_em')
    search_fields = ('pagamento_id', 'referencia', 'email_pagador', 'loja__nome_loja')
    list_select_related = ('loja',)
    date_hierarchy = 'criada_em'
    exclude = ('pix_qr_code',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @display(description="Valor", ordering='valor')
    def valor_em_reais(self, cobranca):
        return reais(cobranca.valor)

    @display(description="Situação", ordering='status', label=CORES_DO_STATUS)
    def situacao(self, cobranca):
        return cobranca.status, cobranca.get_status_display()
