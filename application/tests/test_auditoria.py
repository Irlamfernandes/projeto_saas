from decimal import Decimal
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase, TestCase
from application.auditoria.selectors import registros_do_usuario
from application.auditoria.services import diferencas, fotografar, registrar_alteracao
from infrastructure.models import Acao, LojaModel, RegistroDeAlteracao


class RegistrarAlteracaoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja)

    def test_grava_quem_o_que_e_os_detalhes(self):
        registro = registrar_alteracao(
            loja=self.loja, usuario=self.usuario, acao=Acao.PRODUTO_EDITADO, descricao="Pão", detalhes={'a': 1},
        )
        self.assertEqual((registro.usuario, registro.acao, registro.detalhes), (self.usuario, Acao.PRODUTO_EDITADO, {'a': 1}))

    def test_sem_usuario_logado_fica_sem_usuario(self):
        for usuario in (None, AnonymousUser()):
            with self.subTest(usuario=usuario):
                registro = registrar_alteracao(loja=self.loja, usuario=usuario, acao=Acao.VENDA_REGISTRADA, descricao="x")
                self.assertIsNone(registro.usuario)
                self.assertEqual(registro.detalhes, {})

    def test_descricao_longa_e_cortada(self):
        registro = registrar_alteracao(loja=self.loja, usuario=None, acao=Acao.VENDA_REGISTRADA, descricao="x" * 300)
        self.assertEqual(len(registro.descricao), 255)


class FotografarTest(SimpleTestCase):

    def test_decimal_vira_texto_para_caber_em_json(self):
        produto = SimpleNamespace(nome="Pão", preco_venda=Decimal('10.50'), quantidade_estoque=3)
        self.assertEqual(fotografar(produto, ('nome', 'preco_venda', 'quantidade_estoque')),
                         {'nome': "Pão", 'preco_venda': '10.50', 'quantidade_estoque': 3})

    def test_mesmo_preco_escrito_de_outro_jeito_nao_e_alteracao(self):
        """Regressão: '10' digitado no form contra '10.00' do banco aparecia como mudança de preço."""
        antes = fotografar(SimpleNamespace(preco=Decimal('10.00')), ('preco',))
        depois = fotografar(SimpleNamespace(preco=Decimal('10')), ('preco',))
        self.assertEqual(diferencas(antes, depois), {})

    def test_mais_casas_decimais_sao_preservadas(self):
        self.assertEqual(fotografar(SimpleNamespace(taxa=Decimal('1.2345')), ('taxa',)), {'taxa': '1.2345'})

    def test_diferencas_so_traz_o_que_mudou(self):
        self.assertEqual(diferencas({'nome': "Pão", 'preco': '10'}, {'nome': "Pão", 'preco': '12'}), {'preco': ['10', '12']})


class RegistrosDoUsuarioTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        outra = LojaModel.objects.create(nome_loja="Loja B")
        self.venda = registrar_alteracao(loja=self.loja, usuario=None, acao=Acao.VENDA_REGISTRADA, descricao="v")
        self.pagamento = registrar_alteracao(loja=self.loja, usuario=None, acao=Acao.PAGAMENTO_REGISTRADO, descricao="p")
        registrar_alteracao(loja=outra, usuario=None, acao=Acao.VENDA_REGISTRADA, descricao="outra loja")
        self.usuario = SimpleNamespace(is_superuser=False, loja=self.loja)

    def test_so_da_loja_e_mais_recentes_primeiro(self):
        self.assertEqual(list(registros_do_usuario(self.usuario)), [self.pagamento, self.venda])

    def test_filtra_pela_acao(self):
        self.assertEqual(list(registros_do_usuario(self.usuario, Acao.VENDA_REGISTRADA)), [self.venda])

    def test_texto_do_registro(self):
        self.assertEqual(str(self.venda), "Venda registrada: v")
        self.assertEqual(RegistroDeAlteracao.objects.count(), 3)
