from types import SimpleNamespace
from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase
from interfaces.decorators import loja_required


@loja_required
def _view(request):
    return HttpResponse("ok")


class LojaRequiredTest(SimpleTestCase):

    def _request(self, user):
        request = RequestFactory().get('/qualquer/')
        request.user = user
        return request

    def _usuario(self, **attrs):
        return SimpleNamespace(is_authenticated=True, is_superuser=False, loja=None, **attrs)

    def test_anonimo_e_redirecionado_para_login(self):
        response = _view(self._request(AnonymousUser()))
        self.assertEqual(response.status_code, 302)
        self.assertIn('login', response.url)

    def test_usuario_de_loja_ativa_acessa(self):
        user = self._usuario()
        user.loja = SimpleNamespace(ativo=True)
        self.assertEqual(_view(self._request(user)).content, b"ok")

    def test_usuario_de_loja_inativa_e_bloqueado(self):
        user = self._usuario()
        user.loja = SimpleNamespace(ativo=False)
        with self.assertRaises(PermissionDenied):
            _view(self._request(user))

    def test_preserva_metadados_da_view(self):
        self.assertEqual(_view.__name__, '_view')
