from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory, TestCase

from infrastructure.admin.loja_admin import LojaAdmin
from infrastructure.models.loja_model import LojaModel

User = get_user_model()


class DummyRequest:
    """Classe auxiliar simples para simular o request do Django nos testes do Admin."""
    def __init__(self, user):
        self.user = user


class LojaAdminTest(TestCase):

    def setUp(self):
        # Instancia o AdminSite e a classe LojaAdmin
        self.site = AdminSite()
        self.loja_admin = LojaAdmin(LojaModel, self.site)
        self.factory = RequestFactory()

        # Criação de Lojas de teste
        self.loja1 = LojaModel.objects.create(nome_loja="Loja Alpha", ativo=True)
        self.loja2 = LojaModel.objects.create(nome_loja="Loja Beta", ativo=True)

        # Criação de Usuários respeitando a obrigatoriedade da loja do UsuarioModel
        self.superuser = User.objects.create_superuser(
            username="admin", password="password", email="admin@admin.com"
        )

        # Usuário comum com loja vinculada logo na criação
        self.user_com_loja = User.objects.create_user(
            username="user_loja1", password="password", loja=self.loja1
        )

        # Usuário criado com loja, mas que depois vamos simular que não tem (removendo o atributo para o teste)
        self.user_sem_loja = User.objects.create_user(
            username="user_sem_loja", password="password", loja=self.loja1
        )
        self.user_sem_loja.loja = None  # Simula a ausência de loja após a criação

    # ---------------------------------------------------------
    # Testes de Atributos Básicos do ModelAdmin
    # ---------------------------------------------------------
    def test_admin_configuration(self):
        """Verifica se as configurações básicas do Django Admin estão corretas."""
        self.assertEqual(self.loja_admin.list_display,
                         ('marca', 'nome_loja', 'situacao_do_plano', 'vencimento', 'usuarios', 'ativo', 'criado_em'))
        self.assertEqual(self.loja_admin.search_fields, ('nome_loja',))
        self.assertEqual(self.loja_admin.list_filter, ('ativo', 'vencimento', 'criado_em'))

    def test_so_o_superusuario_muda_o_vencimento_a_mao(self):
        self.assertEqual(self.loja_admin.get_readonly_fields(DummyRequest(user=self.superuser)), ())
        self.assertEqual(self.loja_admin.get_readonly_fields(DummyRequest(user=self.user_com_loja)), ('vencimento',))

    # ---------------------------------------------------------
    # Testes do método get_queryset
    # ---------------------------------------------------------
    def test_get_queryset_as_superuser(self):
        """Superusuário deve visualizar todas as lojas."""
        request = DummyRequest(user=self.superuser)
        qs = self.loja_admin.get_queryset(request)

        self.assertEqual(qs.count(), 2)
        self.assertIn(self.loja1, qs)
        self.assertIn(self.loja2, qs)

    def test_get_queryset_as_user_with_loja(self):
        """Usuário comum com loja vinculada deve visualizar apenas a sua loja."""
        request = DummyRequest(user=self.user_com_loja)
        qs = self.loja_admin.get_queryset(request)

        self.assertEqual(qs.count(), 1)
        self.assertIn(self.loja1, qs)
        self.assertNotIn(self.loja2, qs)

    def test_get_queryset_as_user_without_loja(self):
        """Usuário comum sem loja vinculada não deve visualizar nenhuma loja."""
        request = DummyRequest(user=self.user_sem_loja)
        qs = self.loja_admin.get_queryset(request)

        self.assertEqual(qs.count(), 0)

    # ---------------------------------------------------------
    # Testes de Permissões (Add / Delete)
    # ---------------------------------------------------------
    def test_has_add_permission(self):
        """Apenas superusuários podem adicionar novas lojas."""
        request_super = DummyRequest(user=self.superuser)
        request_user = DummyRequest(user=self.user_com_loja)

        self.assertTrue(self.loja_admin.has_add_permission(request_super))
        self.assertFalse(self.loja_admin.has_add_permission(request_user))

    def test_has_delete_permission(self):
        """Apenas superusuários podem deletar lojas."""
        request_super = DummyRequest(user=self.superuser)
        request_user = DummyRequest(user=self.user_com_loja)

        self.assertTrue(self.loja_admin.has_delete_permission(request_super, obj=self.loja1))
        self.assertFalse(self.loja_admin.has_delete_permission(request_user, obj=self.loja1))

    # ---------------------------------------------------------
    # Testes do método save_model
    # ---------------------------------------------------------
    def test_save_model_as_superuser(self):
        """Superusuário pode salvar qualquer alteração sem restrições."""
        request = DummyRequest(user=self.superuser)
        self.loja1.nome_loja = "Loja Alpha Alterada"

        self.loja_admin.save_model(request, self.loja1, form=None, change=True)  # sem exceção

    def test_save_model_user_modifying_own_loja(self):
        """Usuário comum pode alterar a sua própria loja."""
        request = DummyRequest(user=self.user_com_loja)
        self.loja1.nome_loja = "Meu Nome Novo"

        try:
            self.loja_admin.save_model(request, self.loja1, form=None, change=True)
        except PermissionDenied:
            self.fail("save_model bloqueou indevidamente o usuário alterando sua própria loja.")

    def test_save_model_user_modifying_other_loja_raises_exception(self):
        """Usuário comum tentando alterar uma loja diferente da sua deve receber PermissionDenied."""
        request = DummyRequest(user=self.user_com_loja)
        self.loja2.nome_loja = "Tentativa de roubo"

        with self.assertRaises(PermissionDenied):
            self.loja_admin.save_model(request, self.loja2, form=None, change=True)

    def test_save_model_user_without_loja_raises_exception(self):
        """Funcionário do admin sem loja não salva loja nenhuma (nem chega à tela, mas o servidor também barra)."""
        request = DummyRequest(user=self.user_sem_loja)

        with self.assertRaises(PermissionDenied):
            self.loja_admin.save_model(request, self.loja1, form=None, change=True)
