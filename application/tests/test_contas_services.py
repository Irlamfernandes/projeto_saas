from django.contrib.auth import get_user_model
from django.test import TestCase
from application.contas.services import definir_senha_definitiva
from infrastructure.models import LojaModel


class DefinirSenhaDefinitivaTest(TestCase):

    def test_troca_a_senha_e_libera_o_acesso(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        user = get_user_model().objects.create_user(username="ana", password="temporaria1", loja=loja)

        definir_senha_definitiva(user, "Nova#Senha2026")

        user.refresh_from_db()
        self.assertFalse(user.deve_trocar_senha)
        self.assertTrue(user.check_password("Nova#Senha2026"))
        self.assertFalse(user.check_password("temporaria1"))
