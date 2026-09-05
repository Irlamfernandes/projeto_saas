import secrets
import string
from django.contrib import admin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import path
from django.shortcuts import get_object_or_404, redirect
from django.utils.html import format_html
from infrastructure.models.usuario_model import UsuarioModel

@admin.register(UsuarioModel)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'loja', 'deve_trocar_senha', 'is_staff', 'is_superuser')
    list_filter = ('loja', 'deve_trocar_senha', 'is_staff', 'is_superuser')
    search_fields = ('username', 'email')
    
    fields = ('username', 'loja', 'deve_trocar_senha', 'is_active', 'is_staff', 'is_superuser')
    
    change_form_template = "admin/usuario_change_form.html"

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
                "Senha do usuário <b>{}</b> resetada com sucesso! Nova senha temporária: <strong style='background: #fff; color: #000; padding: 2px 6px; border-radius: 4px;'>{}</strong>",
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
                    "Usuário <b>{}</b> criado com sucesso! Senha temporária gerada: <strong style='background: #fff; color: #000; padding: 2px 6px; border-radius: 4px;'>{}</strong>",
                    obj.username,
                    senha_temporaria
                )
            )
        super().save_model(request, obj, form, change)