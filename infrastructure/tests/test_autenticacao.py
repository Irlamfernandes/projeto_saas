from django.contrib.auth import get_user_model
from django.test import TestCase
from infrastructure.autenticacao import BackendComLoja
from infrastructure.models import LojaModel


class BackendComLojaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.user = get_user_model().objects.create_user(username="ana", password="senha-forte-1", loja=self.loja)

    def test_carrega_usuario_e_loja_numa_unica_consulta(self):
        with self.assertNumQueries(1):
            user = BackendComLoja().get_user(self.user.pk)
            self.assertEqual(user.loja.nome_loja, "Loja A")

    def test_usuario_inexistente(self):
        self.assertIsNone(BackendComLoja().get_user(999999))

    def test_usuario_inativo_nao_e_carregado(self):
        self.user.is_active = False
        self.user.save()
        self.assertIsNone(BackendComLoja().get_user(self.user.pk))

    def test_login_continua_funcionando(self):
        self.assertEqual(BackendComLoja().authenticate(None, username="ana", password="senha-forte-1"), self.user)
