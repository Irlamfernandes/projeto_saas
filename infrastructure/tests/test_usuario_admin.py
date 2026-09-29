from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase
from django.urls import reverse

from infrastructure.admin.usuario_admin import CustomUserAdmin
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.usuario_model import UsuarioModel

User = get_user_model()


class UsuarioAdminTest(TestCase):

    def setUp(self):
        self.site = AdminSite()
        self.user_admin = CustomUserAdmin(UsuarioModel, self.site)
        self.factory = RequestFactory()

        # Criação de lojas
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        # Criação de usuários de teste
        self.superuser = User.objects.create_superuser(
            username="admin", password="password", email="admin@admin.com"
        )

        self.user_loja1 = User.objects.create_user(
            username="user_loja1", password="password", loja=self.loja1
        )

        self.user_loja2 = User.objects.create_user(
            username="user_loja2", password="password", loja=self.loja2
        )

    def _add_session_and_messages(self, request):
        """Método auxiliar para injetar sessão e suporte a mensagens no request simulado."""
        session_middleware = SessionMiddleware(lambda req: None)
        session_middleware.process_request(request)
        request.session.save()

        message_middleware = MessageMiddleware(lambda req: None)
        message_middleware.process_request(request)

    # ---------------------------------------------------------
    # Testes de Atributos Básicos e URLs
    # ---------------------------------------------------------
    def test_admin_configuration(self):
        """Verifica se as configurações visuais do Admin estão corretas."""
        self.assertEqual(self.user_admin.list_display, ('username', 'loja', 'tipo_de_acesso', 'senha', 'is_active', 'last_login'))
        self.assertEqual(self.user_admin.list_filter, ('loja', 'deve_trocar_senha', 'is_active', 'is_staff', 'is_superuser'))
        self.assertEqual(self.user_admin.search_fields, ('username', 'email', 'loja__nome_loja'))
        # Os mesmos campos editáveis de antes, agora separados em seções
        campos = [campo for _, opcoes in self.user_admin.fieldsets for campo in opcoes['fields']]
        self.assertEqual(sorted(campos), sorted(('username', 'loja', 'deve_trocar_senha', 'is_active', 'is_staff', 'is_superuser')))
        self.assertEqual(self.user_admin.change_form_outer_after_template, "admin/usuario_resetar_senha.html")

    def test_get_urls_contains_reset_password(self):
        """Verifica se a URL customizada de reset de senha foi registrada."""
        urls = self.user_admin.get_urls()
        url_names = [u.name for u in urls if hasattr(u, 'name') and u.name]
        self.assertIn('usuario_resetar_senha', url_names)

    # ---------------------------------------------------------
    # Testes da View reset_password_view
    # ---------------------------------------------------------
    def test_reset_password_non_post_raises_permission_denied(self):
        """Requer método POST para resetar a senha; GET deve falhar."""
        request = self.factory.get('/admin/resetar-senha/')
        request.user = self.superuser

        with self.assertRaises(PermissionDenied):
            self.user_admin.reset_password_view(request, self.user_loja1.pk)

    def test_reset_password_common_user_targeting_superuser_raises_exception(self):
        """Usuário comum não pode resetar senha de um superusuário."""
        request = self.factory.post('/admin/resetar-senha/')
        request.user = self.user_loja1

        with self.assertRaises(PermissionDenied):
            self.user_admin.reset_password_view(request, self.superuser.pk)

    def test_reset_password_common_user_targeting_other_loja_raises_exception(self):
        """Usuário comum não pode resetar senha de um usuário de outra loja."""
        request = self.factory.post('/admin/resetar-senha/')
        request.user = self.user_loja1  # Loja 1

        with self.assertRaises(PermissionDenied):
            self.user_admin.reset_password_view(request, self.user_loja2.pk)  # Loja 2

    def test_reset_password_success(self):
        """Superusuário consegue resetar senha de qualquer usuário com sucesso."""
        request = self.factory.post('/admin/resetar-senha/')
        request.user = self.superuser
        self._add_session_and_messages(request)

        response = self.user_admin.reset_password_view(request, self.user_loja1.pk)

        self.user_loja1.refresh_from_db()
        self.assertTrue(self.user_loja1.deve_trocar_senha)

        expected_url = reverse('admin:infrastructure_usuariomodel_change', args=[self.user_loja1.pk])
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, expected_url)

    # ---------------------------------------------------------
    # Testes do método save_model
    # ---------------------------------------------------------
    def test_save_model_common_user_creating_privileged_user_raises_exception(self):
        """Usuário comum não pode criar usuário com privilégios administrativos."""
        request = self.factory.post('/admin/add/')
        request.user = self.user_loja1

        novo_usuario = UsuarioModel(username="hacker", is_staff=True, loja=self.loja1)

        with self.assertRaises(PermissionDenied):
            self.user_admin.save_model(request, novo_usuario, form=None, change=False)

    def test_save_model_creates_temporary_password_on_creation(self):
        """Ao criar um novo usuário, gera senha temporária e define deve_trocar_senha."""
        request = self.factory.post('/admin/add/')
        request.user = self.superuser
        self._add_session_and_messages(request)

        novo_usuario = UsuarioModel(username="novo_user", loja=self.loja1)

        self.user_admin.save_model(request, novo_usuario, form=None, change=False)

        novo_usuario.refresh_from_db()
        self.assertTrue(novo_usuario.deve_trocar_senha)
        self.assertTrue(novo_usuario.has_usable_password())

    def test_save_model_editing_user_keeps_password(self):
        """Editar um usuário que já tem senha não gera senha nova nem pede troca."""
        self.user_loja1.deve_trocar_senha = False
        self.user_loja1.save()
        senha_antes = self.user_loja1.password
        request = self.factory.post('/admin/change/')
        request.user = self.superuser
        self._add_session_and_messages(request)

        self.user_loja1.first_name = "Caixa"
        self.user_admin.save_model(request, self.user_loja1, form=None, change=True)

        self.user_loja1.refresh_from_db()
        self.assertEqual(self.user_loja1.password, senha_antes)
        self.assertFalse(self.user_loja1.deve_trocar_senha)
        self.assertEqual(list(request._messages), [])
