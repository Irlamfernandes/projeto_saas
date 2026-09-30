from django.contrib import admin
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.utils import timezone
from unfold.admin import ModelAdmin
from unfold.decorators import display
from application.lojas.encerramento import PRAZO_DEPOIS_DO_PLANO, apagar_loja, lojas_para_apagar
from infrastructure.models.loja_model import LojaModel

DIAS_PARA_AVISAR = 7


class DadosParaApagar(admin.SimpleListFilter):
    """Política de privacidade: 90 dias depois do fim do plano, os dados da loja são apagados."""
    title = "dados"
    parameter_name = 'dados'

    def lookups(self, request, model_admin):
        return [('apagar', "Plano vencido há mais de 90 dias")]

    def queryset(self, request, queryset):
        return lojas_para_apagar(queryset) if self.value() == 'apagar' else queryset


@admin.register(LojaModel)
class LojaAdmin(ModelAdmin):
    list_display = ('marca', 'nome_loja', 'situacao_do_plano', 'vencimento', 'usuarios', 'ativo', 'criado_em')
    list_display_links = ('marca', 'nome_loja')
    search_fields = ('nome_loja',)
    list_filter = ('ativo', DadosParaApagar, 'vencimento', 'criado_em')
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

    def get_readonly_fields(self, request, obj=None):
        # O vencimento só muda por pagamento confirmado; à mão, só o superusuário (casos especiais).
        return () if request.user.is_superuser else ('vencimento',)

    def has_add_permission(self, request):
        return request.user.is_superuser

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser

    def get_deleted_objects(self, objs, request):
        """Apagar a loja inteira (só o superusuário pode) leva tudo o que é dela, inclusive o que não se apaga
        avulso: histórico e cobranças (sem exclusão no admin) e itens de venda, de compra e perdas (que protegem o
        produto; `apagar_loja` tira esses antes). Por isso a confirmação não trava em nenhum deles."""
        apagados, contagem, _sem_permissao, _protegidos = super().get_deleted_objects(objs, request)
        return apagados, contagem, set(), []

    def delete_model(self, request, obj):
        apagar_loja(obj)

    def delete_queryset(self, request, queryset):
        for loja in queryset:
            apagar_loja(loja)

    def save_model(self, request, obj, form, change):
        # Fora o superusuário, cada um só salva a própria loja; quem não tem loja não salva nenhuma.
        if not request.user.is_superuser:
            loja_do_usuario = getattr(request.user, 'loja', None)
            if loja_do_usuario is None or obj.pk != loja_do_usuario.pk:
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
        if dias < -PRAZO_DEPOIS_DO_PLANO.days:
            return 'vencido', "Vencido há +90 dias: apagar"
        if dias < 0:
            return 'vencido', "Vencido"
        if dias <= DIAS_PARA_AVISAR:
            return 'vencendo', "Vence em breve"
        return 'em_dia', "Em dia"

    @display(description="Usuários", ordering='total_de_usuarios')
    def usuarios(self, loja):
        return getattr(loja, 'total_de_usuarios', loja.usuarios.count())
