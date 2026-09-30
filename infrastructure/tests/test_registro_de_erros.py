import json
import logging
import sys
from contextlib import contextmanager
from unittest.mock import patch
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import Client, RequestFactory, TestCase, override_settings
from django.urls import path
from infrastructure.models import ErroDoSistema, LojaModel
from infrastructure.registro_de_erros import (
    RAIZ, GuardarErroNoBanco, SemAvisosDeSeguranca, _do_projeto, ocorrencia_do_registro,
)


class ErroDoTeste(Exception):
    pass


def view_que_quebra(request):
    raise RuntimeError("deu ruim na tela")


urlpatterns = [path('quebra/', view_que_quebra)]


@contextmanager
def guardando_erros():
    """Na suíte o handler fica desligado (config/settings_test.py); aqui ele é ligado como na produção."""
    handler = GuardarErroNoBanco(level=logging.ERROR)
    raiz = logging.getLogger()
    raiz.addHandler(handler)
    try:
        yield handler
    finally:
        raiz.removeHandler(handler)


def _registro(nome='application.teste', mensagem="falhou", exc_info=None, request=None):
    registro = logging.LogRecord(nome, logging.ERROR, __file__, 42, mensagem, (), exc_info)
    if request is not None:
        registro.request = request
    return registro


def _exc_info(excecao):
    try:
        raise excecao
    except Exception:  # noqa: BLE001
        return sys.exc_info()


def _exc_info_de(funcao, *argumentos):
    try:
        funcao(*argumentos)
    except Exception:  # noqa: BLE001
        return sys.exc_info()


class OcorrenciaDoRegistroTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja)

    def test_excecao_do_python_aponta_para_o_nosso_codigo(self):
        ocorrencia = ocorrencia_do_registro(_registro(exc_info=_exc_info(ValueError("valor ruim"))))
        self.assertEqual((ocorrencia.tipo, ocorrencia.mensagem), ('ValueError', "valor ruim"))
        linha_do_raise = _exc_info.__code__.co_firstlineno + 2
        self.assertEqual(ocorrencia.local, f"infrastructure/tests/test_registro_de_erros.py:{linha_do_raise} em _exc_info")
        self.assertIn("ValueError: valor ruim", ocorrencia.detalhes)

    def test_excecao_propria_leva_o_modulo_no_nome(self):
        ocorrencia = ocorrencia_do_registro(_registro(exc_info=_exc_info(ErroDoTeste("x"))))
        self.assertTrue(ocorrencia.tipo.endswith("test_registro_de_erros.ErroDoTeste"))

    def test_erro_so_dentro_de_biblioteca_mostra_o_arquivo_dela(self):
        tipo, excecao, tb = _exc_info_de(json.loads, '{')
        ocorrencia = ocorrencia_do_registro(_registro(exc_info=(tipo, excecao, tb.tb_next)))  # só os quadros do json
        self.assertRegex(ocorrencia.local, r'^decoder\.py:\d+ em raw_decode$')

    def test_sem_excecao_usa_a_mensagem_e_a_linha_do_log(self):
        ocorrencia = ocorrencia_do_registro(_registro(mensagem="upload falhou", exc_info=(None, None, None)))
        self.assertEqual((ocorrencia.tipo, ocorrencia.mensagem), ('application.teste', "upload falhou"))
        self.assertEqual(ocorrencia.local, "infrastructure/tests/test_registro_de_erros.py:42")
        self.assertEqual(ocorrencia.detalhes, '')

    def test_tela_loja_e_usuario_de_quem_estava_logado(self):
        request = RequestFactory().post('/vendas/?cliente=123')
        request.user = self.usuario
        ocorrencia = ocorrencia_do_registro(_registro(request=request))
        self.assertEqual((ocorrencia.caminho, ocorrencia.metodo), ('/vendas/', 'POST'))  # sem os parâmetros
        self.assertEqual((ocorrencia.loja_id, ocorrencia.usuario_id), (self.loja.pk, self.usuario.pk))

    def test_sem_usuario_logado(self):
        anonimo = RequestFactory().get('/login/')
        anonimo.user = AnonymousUser()
        sem_usuario = RequestFactory().get('/login/')
        for request in (anonimo, sem_usuario):
            ocorrencia = ocorrencia_do_registro(_registro(request=request))
            self.assertEqual((ocorrencia.caminho, ocorrencia.loja_id, ocorrencia.usuario_id), ('/login/', None, None))
        self.assertEqual(ocorrencia_do_registro(_registro()).caminho, '')

    def test_bibliotecas_instaladas_nao_contam_como_codigo_do_projeto(self):
        self.assertTrue(_do_projeto(str(RAIZ / 'application' / 'x.py')))
        self.assertFalse(_do_projeto(str(RAIZ / 'venv' / 'lib' / 'python3.12' / 'site-packages' / 'django' / 'x.py')))
        self.assertFalse(_do_projeto('/usr/lib/python3/x.py'))


class GuardarErroNoBancoTest(TestCase):

    def test_grava_o_erro(self):
        GuardarErroNoBanco().emit(_registro(exc_info=_exc_info(ValueError("x"))))
        self.assertEqual(ErroDoSistema.objects.get().tipo, 'ValueError')

    def test_falha_ao_gravar_nao_derruba_nada(self):
        handler = GuardarErroNoBanco()
        with patch('application.erros.services.registrar_erro', side_effect=RuntimeError("banco fora")), \
                patch.object(handler, 'handleError') as handle_error:
            handler.emit(_registro())
        handle_error.assert_called_once()
        self.assertFalse(hasattr(GuardarErroNoBanco._gravando, 'ativo'))  # a trava sai no fim

    def test_erro_durante_a_gravacao_nao_entra_em_laco(self):
        GuardarErroNoBanco._gravando.ativo = True
        try:
            GuardarErroNoBanco().emit(_registro())
        finally:
            del GuardarErroNoBanco._gravando.ativo
        self.assertFalse(ErroDoSistema.objects.exists())

    def test_avisos_de_seguranca_ficam_so_no_console(self):
        filtro = SemAvisosDeSeguranca()
        self.assertFalse(filtro.filter(_registro('django.security.DisallowedHost')))
        self.assertTrue(filtro.filter(_registro('django.request')))


@override_settings(ROOT_URLCONF=__name__)
class PaginaQueQuebraTest(TestCase):
    """De ponta a ponta: a tela dá erro 500 e o erro aparece na tabela, com a tela e quem estava usando."""

    def test_erro_500_vira_registro(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=loja)
        cliente = Client(raise_request_exception=False)
        cliente.force_login(usuario)
        with guardando_erros():
            self.assertEqual(cliente.get('/quebra/?x=1').status_code, 500)
            cliente.get('/quebra/')

        erro = ErroDoSistema.objects.get()
        self.assertEqual((erro.tipo, erro.mensagem, erro.caminho, erro.metodo), ('RuntimeError', "deu ruim na tela", '/quebra/', 'GET'))
        linha = view_que_quebra.__code__.co_firstlineno + 1
        self.assertEqual(erro.local, f"infrastructure/tests/test_registro_de_erros.py:{linha} em view_que_quebra")
        self.assertEqual((erro.loja, erro.usuario, erro.ocorrencias), (loja, usuario, 2))


class ConfiguracaoDoLogTest(TestCase):

    def test_producao_manda_para_o_console_e_para_a_tabela(self):
        from config import settings as producao
        raiz = producao.LOGGING['root']
        self.assertEqual(raiz['handlers'], ['console', 'erros_do_sistema'])
        self.assertEqual(producao.LOGGING['handlers']['erros_do_sistema']['level'], 'ERROR')
        self.assertTrue(producao.LOGGING['loggers']['django']['propagate'])

    def test_nos_testes_so_o_console(self):
        self.assertEqual(settings.LOGGING['root']['handlers'], ['console'])
