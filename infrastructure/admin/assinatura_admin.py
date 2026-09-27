from django.contrib import admin
from infrastructure.models import Cobranca, Plano


@admin.register(Plano)
class PlanoAdmin(admin.ModelAdmin):
    """Preços e planos à venda. Só o superusuário mexe (as permissões padrão do Django cuidam disso)."""
    list_display = ('nome', 'quantidade', 'unidade', 'preco', 'ativo', 'ordem')
    list_editable = ('preco', 'ativo', 'ordem')


@admin.register(Cobranca)
class CobrancaAdmin(admin.ModelAdmin):
    """Só leitura: uma cobrança só muda pela confirmação do Mercado Pago."""
    list_display = ('criada_em', 'loja', 'plano_nome', 'valor', 'status', 'vencimento_novo')
    list_filter = ('status', 'loja')
    search_fields = ('pagamento_id', 'referencia', 'email_pagador')
    list_select_related = ('loja',)
    exclude = ('pix_qr_code',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
