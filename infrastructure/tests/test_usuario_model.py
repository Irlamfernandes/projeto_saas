from django.core.exceptions import ValidationError
from django.test import TestCase
from infrastructure.models.loja_model import LojaModel
from infrastructure.models.usuario_model import UsuarioModel


class UsuarioModelTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja Principal", ativo=True)

    # ---------------------------------------------------------
    # Testes do Validador de Username
    # ---------------------------------------------------------
    def test_username_validator_accepts_spaces_and_special_chars(self):
        """O validador customizado deve aceitar espaços e caracteres permitidos."""
        user = UsuarioModel(
            username="João Silva @123",
            loja=self.loja
        )
        # Não deve lançar erro de validação para o username
        try:
            user.full_clean()
        except ValidationError as e:
            self.assertNotIn('username', e.error_dict)

    def test_username_validator_rejects_invalid_chars(self):
        """O validador deve rejeitar caracteres não permitidos como exclamação ou hashtags."""
        user = UsuarioModel(
            username="Joao!Silva#",
            loja=self.loja
        )
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn('username', ctx.exception.error_dict)

    # ---------------------------------------------------------
    # Testes de Validação da Loja (clean)
    # ---------------------------------------------------------
    def test_common_user_requires_loja(self):
        """Usuário comum sem loja deve disparar ValidationError."""
        user = UsuarioModel(
            username="usuario_comum",
            loja=None,
            is_staff=False,
            is_superuser=False
        )
        with self.assertRaises(ValidationError) as ctx:
            user.full_clean()
        self.assertIn('loja', ctx.exception.error_dict)

    def test_staff_user_can_have_no_loja(self):
        """Usuário staff sem loja não deve disparar erro de validação."""
        user = UsuarioModel(
            username="usuario_staff",
            loja=None,
            is_staff=True,
            is_superuser=False
        )
        try:
            user.full_clean()
        except ValidationError as e:
            self.assertNotIn('loja', e.error_dict)

    def test_superuser_can_have_no_loja(self):
        """Superusuário sem loja não deve disparar erro de validação."""
        user = UsuarioModel(
            username="usuario_superuser",
            loja=None,
            is_staff=True,
            is_superuser=True
        )
        try:
            user.full_clean()
        except ValidationError as e:
            self.assertNotIn('loja', e.error_dict)

    # ---------------------------------------------------------
    # Testes do __str__ e Defaults
    # ---------------------------------------------------------
    def test_usuario_str_with_loja(self):
        """O método __str__ deve exibir o nome do usuário e da loja."""
        user = UsuarioModel.objects.create_user(
            username="caique", password="password", loja=self.loja
        )
        self.assertEqual(str(user), "caique (Loja Principal)")

    def test_usuario_str_without_loja(self):
        """O método __str__ deve exibir Admin Global quando não houver loja."""
        user = UsuarioModel.objects.create_superuser(
            username="admin_global", password="password", email="admin@email.com"
        )
        self.assertEqual(str(user), "admin_global (Admin Global)")

    def test_deve_trocar_senha_default(self):
        """O campo deve_trocar_senha deve iniciar como True por padrão."""
        user = UsuarioModel.objects.create_user(
            username="novo_usuario", password="password", loja=self.loja
        )
        self.assertTrue(user.deve_trocar_senha)
