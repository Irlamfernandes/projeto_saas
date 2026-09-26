from unittest.mock import Mock
from django import forms
from django.contrib.messages import get_messages
from django.contrib.messages.storage.fallback import FallbackStorage
from django.test import RequestFactory, SimpleTestCase
from application.exceptions import RegraDeNegocioError
from interfaces.views.comum import executar_formulario


class _Form(forms.Form):
    nome = forms.CharField(error_messages={'required': "Informe o nome."})


class ExecutarFormularioTest(SimpleTestCase):

    def setUp(self):
        self.request = RequestFactory().post('/')
        self.request.session = {}
        self.request._messages = FallbackStorage(self.request)

    def _mensagens(self):
        return [(m.level_tag, str(m)) for m in get_messages(self.request)]

    def test_form_invalido_nao_executa_acao(self):
        acao = Mock()

        ok = executar_formulario(self.request, _Form({}), acao, "feito")

        self.assertFalse(ok)
        acao.assert_not_called()
        self.assertEqual(self._mensagens(), [('error', "Informe o nome.")])

    def test_erro_de_negocio_vira_mensagem(self):
        acao = Mock(side_effect=RegraDeNegocioError("sem estoque"))

        ok = executar_formulario(self.request, _Form({'nome': 'x'}), acao, "feito")

        self.assertFalse(ok)
        self.assertEqual(self._mensagens(), [('error', "sem estoque")])

    def test_sucesso(self):
        ok = executar_formulario(self.request, _Form({'nome': 'x'}), Mock(), "feito")

        self.assertTrue(ok)
        self.assertEqual(self._mensagens(), [('success', "feito")])

    def test_outras_excecoes_nao_sao_engolidas(self):
        acao = Mock(side_effect=ValueError("bug"))
        with self.assertRaises(ValueError):
            executar_formulario(self.request, _Form({'nome': 'x'}), acao, "feito")
