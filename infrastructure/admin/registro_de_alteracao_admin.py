import json
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display
from infrastructure.models import Acao, RegistroDeAlteracao
from infrastructure.utils.dados_pessoais import mascarar

# Contatos dos clientes das lojas: a loja vê no relatório dela; o admin da CorsariosCode não precisa ver.
CONTATOS = ('telefone', 'cpf', 'email', 'endereco')

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
    """Só leitura: o histórico não pode ser criado, editado nem apagado à mão. Os contatos dos clientes ficam
    escondidos (LGPD: o admin vê o que aconteceu e quando, não o telefone de quem comprou)."""
    list_display = ('data', 'loja', 'usuario', 'tipo', 'descricao')
    fields = ('data', 'loja', 'usuario', 'acao', 'descricao', 'detalhes_sem_contatos')
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

    @display(description="Detalhes")
    def detalhes_sem_contatos(self, registro):
        texto = json.dumps(sem_contatos(registro.detalhes), ensure_ascii=False, indent=2)
        return format_html('<pre class="whitespace-pre-wrap text-xs">{}</pre>', mascarar(texto))


def sem_contatos(valor):
    """Os mesmos detalhes, com telefone, CPF, e-mail e endereço trocados por "(oculto)" em qualquer nível."""
    if isinstance(valor, dict):
        return {chave: '(oculto)' if chave in CONTATOS else sem_contatos(item) for chave, item in valor.items()}
    if isinstance(valor, list):
        return [sem_contatos(item) for item in valor]
    return valor
