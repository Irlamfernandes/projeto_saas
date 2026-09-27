from datetime import date
from types import SimpleNamespace
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from interfaces.context_processors import plano


class PlanoContextProcessorTest(SimpleTestCase):

    def test_usuario_de_loja_recebe_a_situacao_do_plano(self):
        usuario = SimpleNamespace(is_authenticated=True, is_superuser=False, loja=SimpleNamespace(vencimento=date(2999, 1, 1)))
        situacao = plano(SimpleNamespace(user=usuario))['plano']
        self.assertEqual(situacao.vencimento, date(2999, 1, 1))

    def test_sem_plano_para_anonimo_superusuario_ou_sem_usuario(self):
        casos = [
            SimpleNamespace(user=AnonymousUser()),
            SimpleNamespace(user=SimpleNamespace(is_authenticated=True, is_superuser=True, loja=None)),
            SimpleNamespace(),
        ]
        for request in casos:
            with self.subTest(request=request):
                self.assertEqual(plano(request), {'plano': None})
