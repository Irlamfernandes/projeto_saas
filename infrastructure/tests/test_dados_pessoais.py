import logging
from django.contrib.admin.sites import AdminSite
from django.test import SimpleTestCase, TestCase
from application.erros.services import Ocorrencia, registrar_erro
from infrastructure.admin.registro_de_alteracao_admin import RegistroDeAlteracaoAdmin, sem_contatos
from infrastructure.models import RegistroDeAlteracao
from infrastructure.registro_de_erros import SemDadosPessoais
from infrastructure.utils.dados_pessoais import mascarar


class MascararTest(SimpleTestCase):

    def test_telefones_documentos_e_emails(self):
        casos = {
            'Key (telefone)=(24999998888) already exists': 'Key (telefone)=[número]) already exists',
            'ligar (24) 99999-8888 ou +55 24 99999-8888': 'ligar [número] ou [número]',
            'cpf 123.456.789-00, cartão 4111 1111 1111 1111': 'cpf [número], cartão [número]',
            'escreva para maria.silva+loja@gmail.com.br': 'escreva para [e-mail]',
        }
        for texto, esperado in casos.items():
            with self.subTest(texto):
                self.assertEqual(mascarar(texto), esperado)

    def test_o_resto_fica(self):
        for texto in ('File "/app/x.py", line 1234, in f', 'Venda #1234567', 'em 2026-09-29 10:00:00', ''):
            with self.subTest(texto):
                self.assertEqual(mascarar(texto), texto)
        self.assertEqual(mascarar(None), '')

    def test_console_sai_mascarado(self):
        formato = SemDadosPessoais('{levelname}: {message}', style='{')
        registro = logging.LogRecord('x', logging.ERROR, __file__, 1, 'cliente %s', ('24999998888',), None)
        self.assertEqual(formato.format(registro), 'ERROR: cliente [número]')


class ErroSemDadosPessoaisTest(TestCase):

    def test_tela_de_erros_recebe_a_mensagem_mascarada(self):
        erro = registrar_erro(Ocorrencia('IntegrityError', 'telefone 24999998888 de maria@x.com',
                                         detalhes='Traceback...\nIntegrityError: 24999998888'))
        self.assertEqual(erro.mensagem, 'telefone [número] de [e-mail]')
        self.assertNotIn('24999998888', erro.detalhes)


class HistoricoNoAdminTest(SimpleTestCase):

    def test_contatos_ficam_ocultos_em_qualquer_nivel(self):
        detalhes = {
            'cliente': {'nome': 'Maria', 'telefone': '249', 'email': 'm@x.com', 'endereco': 'Rua A'},
            'alteracoes': {'telefone': ['1', '2'], 'nome': ['Maria', 'Maria S.']},
            'lista': [{'email': 'a@b.c'}, 3],
        }
        self.assertEqual(sem_contatos(detalhes), {
            'cliente': {'nome': 'Maria', 'telefone': '(oculto)', 'email': '(oculto)', 'endereco': '(oculto)'},
            'alteracoes': {'telefone': '(oculto)', 'nome': ['Maria', 'Maria S.']},
            'lista': [{'email': '(oculto)'}, 3],
        })

    def test_tela_mostra_os_detalhes_sem_contatos_e_escapados(self):
        admin = RegistroDeAlteracaoAdmin(RegistroDeAlteracao, AdminSite())
        registro = RegistroDeAlteracao(detalhes={'cliente': {'nome': '<b>Ana</b>', 'telefone': '24999998888'},
                                                 'observacao': 'ligar 24988887777'})
        html = admin.detalhes_sem_contatos(registro)
        self.assertIn('&lt;b&gt;Ana&lt;/b&gt;', html)
        self.assertIn('(oculto)', html)
        self.assertNotIn('24999998888', html)
        self.assertNotIn('24988887777', html)  # número solto num texto livre também sai
