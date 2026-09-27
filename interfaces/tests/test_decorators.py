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
        return SimpleNamespace(is_authenticated=True, is_superuser=False, loja=None, deve_trocar_senha=False, **attrs)

    def test_anonimo_e_redirecionado_para_login(self):
        response = _view(self._request(AnonymousUser()))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/login/?next=/qualquer/')

    def test_usuario_de_loja_ativa_acessa(self):
        user = self._usuario()
        user.loja = SimpleNamespace(ativo=True)
        self.assertEqual(_view(self._request(user)).content, b"ok")

    def test_usuario_de_loja_inativa_e_bloqueado(self):
        user = self._usuario()
        user.loja = SimpleNamespace(ativo=False)
        with self.assertRaises(PermissionDenied):
            _view(self._request(user))

    def test_senha_temporaria_obriga_a_troca_antes_de_tudo(self):
        """Regressão: com senha temporária dava para ir direto ao /dashboard/ e nunca trocá-la."""
        user = self._usuario()
        user.loja = SimpleNamespace(ativo=True)
        user.deve_trocar_senha = True

        response = _view(self._request(user))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, '/alterar-senha/')

    def test_preserva_metadados_da_view(self):
        self.assertEqual(_view.__name__, '_view')


class TravaDoPlanoVencidoTest(SimpleTestCase):
    """Loja com o plano vencido só consulta: qualquer envio de formulário volta com aviso e nada é feito."""

    def setUp(self):
        self.chamadas = []

        def view(request):
            self.chamadas.append(request.method)
            return HttpResponse("ok")

        self.view = loja_required(view)
        self.view_liberada = loja_required(trava_plano_vencido=False)(view)

    def _request(self, metodo='post', vencido=True, **extra):
        from datetime import timedelta
        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.utils import timezone
        request = getattr(RequestFactory(), metodo)('/vendas/', **extra)
        vencimento = timezone.localdate() - timedelta(days=1 if vencido else 0)
        request.user = SimpleNamespace(
            is_authenticated=True, is_superuser=False, deve_trocar_senha=False,
            loja=SimpleNamespace(ativo=True, vencimento=vencimento),
        )
        request.session = {}
        request._messages = FallbackStorage(request)
        return request

    def test_envio_com_plano_vencido_volta_para_a_tela_anterior_com_aviso(self):
        request = self._request(HTTP_REFERER='http://testserver/dashboard/produtos/')
        response = self.view(request)

        self.assertEqual((response.status_code, response.url), (302, 'http://testserver/dashboard/produtos/'))
        self.assertEqual(self.chamadas, [])
        self.assertIn("Seu plano venceu e nada foi salvo", str(list(request._messages)[0]))

    def test_sem_tela_anterior_segura_volta_para_o_inicio(self):
        for extra in ({}, {'HTTP_REFERER': 'https://site-malicioso.com/'}):
            with self.subTest(extra=extra):
                self.assertEqual(self.view(self._request(**extra)).url, '/dashboard/')

    def test_consultar_continua_liberado(self):
        self.assertEqual(self.view(self._request('get')).content, b"ok")

    def test_plano_em_dia_envia_normalmente(self):
        self.assertEqual(self.view(self._request(vencido=False)).content, b"ok")

    def test_telas_liberadas_funcionam_mesmo_vencido(self):
        self.assertEqual(self.view_liberada(self._request()).content, b"ok")
