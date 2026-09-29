from datetime import timedelta
from django.test import TestCase
from django.utils import timezone
from application.erros.services import LIMITE_DA_MENSAGEM, LIMITE_DOS_DETALHES, Ocorrencia, registrar_erro
from infrastructure.models import ErroDoSistema, LojaModel


class AssinaturaTest(TestCase):

    def test_mesmo_tipo_no_mesmo_ponto_do_codigo_e_o_mesmo_erro(self):
        um = Ocorrencia('ValueError', mensagem="a", local="x.py:1 em f", caminho='/a/')
        outro = Ocorrencia('ValueError', mensagem="b", local="x.py:1 em f", caminho='/b/')
        self.assertEqual(um.assinatura, outro.assinatura)
        self.assertNotEqual(um.assinatura, Ocorrencia('KeyError', local="x.py:1 em f").assinatura)

    def test_sem_ponto_do_codigo_a_mensagem_separa(self):
        self.assertNotEqual(Ocorrencia('logger', mensagem="a").assinatura, Ocorrencia('logger', mensagem="b").assinatura)


class RegistrarErroTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.agora = timezone.now()

    def test_primeira_vez_abre_um_registro(self):
        erro = registrar_erro(Ocorrencia(
            'ValueError', "ruim", "x.py:1 em f", "Traceback", '/vendas/', 'POST', self.loja.pk, None,
        ), self.agora)
        self.assertEqual((erro.tipo, erro.mensagem, erro.local, erro.caminho, erro.metodo), (
            'ValueError', "ruim", "x.py:1 em f", '/vendas/', 'POST',
        ))
        self.assertEqual((erro.loja, erro.ocorrencias, erro.primeira_vez, erro.ultima_vez), (self.loja, 1, self.agora, self.agora))
        self.assertFalse(erro.resolvido)
        self.assertEqual(str(erro), "ValueError · x.py:1 em f")

    def test_repeticao_soma_e_guarda_os_dados_da_ultima(self):
        primeiro = registrar_erro(Ocorrencia('ValueError', "a", "x.py:1 em f", caminho='/a/'), self.agora)
        depois = self.agora + timedelta(minutes=5)
        segundo = registrar_erro(Ocorrencia('ValueError', "b", "x.py:1 em f", caminho='/b/'), depois)
        self.assertEqual(segundo.pk, primeiro.pk)
        self.assertEqual((segundo.ocorrencias, segundo.mensagem, segundo.caminho), (2, "b", '/b/'))
        self.assertEqual((segundo.primeira_vez, segundo.ultima_vez), (self.agora, depois))
        self.assertEqual(ErroDoSistema.objects.count(), 1)

    def test_erro_resolvido_que_volta_abre_outro(self):
        antigo = registrar_erro(Ocorrencia('ValueError', local="x.py:1 em f"))
        ErroDoSistema.objects.filter(pk=antigo.pk).update(resolvido=True)
        novo = registrar_erro(Ocorrencia('ValueError', local="x.py:1 em f"))
        self.assertNotEqual(novo.pk, antigo.pk)
        self.assertEqual(novo.ocorrencias, 1)

    def test_textos_enormes_sao_cortados(self):
        erro = registrar_erro(Ocorrencia(
            'E' * 300, 'm' * 5000, 'l' * 400, 'inicio' + 'd' * LIMITE_DOS_DETALHES + 'FIM', 'c' * 900, 'METODOLONGO',
        ))
        self.assertEqual(len(erro.mensagem), LIMITE_DA_MENSAGEM)
        self.assertTrue(erro.detalhes.endswith('FIM'))  # o fim do traceback é o que interessa
        self.assertEqual(len(erro.detalhes), LIMITE_DOS_DETALHES)
        self.assertEqual((len(erro.tipo), len(erro.local), len(erro.caminho), erro.metodo), (200, 300, 500, 'METODOLONG'))
        self.assertEqual(erro.primeira_vez, erro.ultima_vez)
