import secrets
import string
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import path
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html
from unfold.admin import ModelAdmin
from unfold.decorators import display
from infrastructure.models.usuario_model import UsuarioModel

SENHA_EM_DESTAQUE = "<strong style='background: #fff; color: #000; padding: 2px 6px; border-radius: 4px;'>{}</strong>"

@admin.register(UsuarioModel)
class CustomUserAdmin(ModelAdmin):
    list_display = ('username', 'loja', 'tipo_de_acesso', 'senha', 'is_active', 'last_login')
    list_filter = ('loja', 'deve_trocar_senha', 'is_active', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email', 'loja__nome_loja')
    list_select_related = ('loja',)

    fieldsets = (
        ("Acesso", {'fields': ('username', 'loja', 'is_active'),
                    'description': "Ao criar o usuário, o sistema gera uma senha temporária e mostra aqui em cima."}),
        ("Senha", {'fields': ('deve_trocar_senha',)}),
        ("Permissões", {'fields': ('is_staff', 'is_superuser'),
                        'description': "Equipe acessa este admin; superusuário acessa tudo, de todas as lojas."}),
    )

    # Botão de resetar senha, num formulário próprio abaixo do formulário de edição.
    change_form_outer_after_template = "admin/usuario_resetar_senha.html"

    @display(description="Acesso", label={'superusuario': 'danger', 'equipe': 'info', 'loja': 'success'})
    def tipo_de_acesso(self, usuario):
        if usuario.is_superuser:
            return 'superusuario', "Superusuário"
        if usuario.is_staff:
            return 'equipe', "Equipe"
        return 'loja', "Loja"

    @display(description="Senha", label={'trocar': 'warning', 'ok': None})
    def senha(self, usuario):
        return ('trocar', "Precisa trocar") if usuario.deve_trocar_senha else ('ok', "Definida")

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:user_id>/resetar-senha/',
                self.admin_site.admin_view(self.reset_password_view),
                name='usuario_resetar_senha',
            ),
        ]
        return custom_urls + urls

    def reset_password_view(self, request, user_id):
        if request.method != 'POST':
            raise PermissionDenied("Método não permitido para esta operação.")

        user = get_object_or_404(UsuarioModel, pk=user_id)

        if not request.user.is_superuser and user.is_superuser:
            raise PermissionDenied("Você não tem permissão para alterar as credenciais de um superusuário.")

        if not request.user.is_superuser and request.user.loja and user.loja != request.user.loja:
            raise PermissionDenied("Acesso negado: Este usuário pertence a outra loja.")

        alphabet = string.ascii_letters + string.digits
        nova_senha = ''.join(secrets.choice(alphabet) for _ in range(8))
        user.set_password(nova_senha)
        user.deve_trocar_senha = True
        user.save(update_fields=['password', 'deve_trocar_senha'])

        messages.success(
            request,
            format_html(
                "Senha do usuário <b>{}</b> resetada com sucesso! Nova senha temporária: " + SENHA_EM_DESTAQUE,
                user.username,
                nova_senha
            )
        )
        return redirect('admin:infrastructure_usuariomodel_change', user.pk)

    def save_model(self, request, obj, form, change):
        if not change and not request.user.is_superuser and (obj.is_superuser or obj.is_staff):
            raise PermissionDenied("Você não tem permissão para criar usuários com privilégios administrativos.")

        if not change or not obj.pk or not obj.has_usable_password():
            alphabet = string.ascii_letters + string.digits
            senha_temporaria = ''.join(secrets.choice(alphabet) for _ in range(8))
            obj.set_password(senha_temporaria)
            obj.deve_trocar_senha = True

            messages.success(
                request,
                format_html(
                    "Usuário <b>{}</b> criado com sucesso! Senha temporária gerada: " + SENHA_EM_DESTAQUE,
                    obj.username,
                    senha_temporaria
                )
            )
        super().save_model(request, obj, form, change)
