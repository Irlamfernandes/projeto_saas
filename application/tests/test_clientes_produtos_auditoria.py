from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from application.clientes.services import atualizar_cliente, cadastrar_cliente, registrar_pagamento
from application.produtos.services import atualizar_produto, cadastrar_produto
from infrastructure.models import Acao, Cliente, LojaModel, Produto, RegistroDeAlteracao
from tests.apoio import StorageFalso, imagem_de_teste


class RegistroNosCadastrosTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.usuario = get_user_model().objects.create_user(username="caixa", password="x", loja=self.loja)

    def registro(self, acao):
        return RegistroDeAlteracao.objects.get(acao=acao)

    def test_cliente_cadastrado_e_editado(self):
        cliente = cadastrar_cliente(Cliente(loja=self.loja, nome="Ana", telefone="1"), usuario=self.usuario)
        cliente.telefone = "2"
        atualizar_cliente(cliente, usuario=self.usuario)

        self.assertEqual(self.registro(Acao.CLIENTE_CADASTRADO).detalhes['cliente']['nome'], "Ana")
        self.assertEqual(self.registro(Acao.CLIENTE_EDITADO).detalhes, {'alteracoes': {'telefone': ["1", "2"]}})

    def test_salvar_cliente_sem_mudar_nada_nao_registra(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")
        atualizar_cliente(cliente, usuario=self.usuario)
        self.assertFalse(RegistroDeAlteracao.objects.exists())

    def test_pagamento_registra_valor_e_forma(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")
        registrar_pagamento(cliente, valor=Decimal('12.50'), forma_pagamento='pix', usuario=self.usuario)
        self.assertEqual(self.registro(Acao.PAGAMENTO_REGISTRADO).descricao, "Ana · R$ 12,50 · Pix")

    def test_pagamento_sem_forma_diz_que_nao_foi_informada(self):
        cliente = Cliente.objects.create(loja=self.loja, nome="Ana")
        registrar_pagamento(cliente, valor=Decimal('1'))
        self.assertTrue(self.registro(Acao.PAGAMENTO_REGISTRADO).descricao.endswith("forma não informada"))

    def test_produto_cadastrado_e_mudanca_de_preco(self):
        produto = cadastrar_produto(Produto(loja=self.loja, nome="Pão", preco_venda=Decimal('10')), usuario=self.usuario,
                                    storage=StorageFalso())
        produto.preco_venda = Decimal('12.00')
        atualizar_produto(produto, storage=StorageFalso(), usuario=self.usuario)

        self.assertEqual(self.registro(Acao.PRODUTO_CADASTRADO).detalhes['fotos'], 0)
        self.assertEqual(self.registro(Acao.PRODUTO_EDITADO).detalhes, {'alteracoes': {'preco_venda': ['10.00', '12.00']}})

    def test_produto_so_com_fotos_novas_tambem_registra(self):
        produto = Produto.objects.create(loja=self.loja, nome="Pão", preco_venda=Decimal('10'))
        with self.captureOnCommitCallbacks(execute=True):
            atualizar_produto(produto, [imagem_de_teste()], storage=StorageFalso(), usuario=self.usuario)
        self.assertEqual(self.registro(Acao.PRODUTO_EDITADO).detalhes, {'alteracoes': {}, 'fotos': {'adicionadas': 1, 'removidas': 0}})

    def test_produto_salvo_sem_mudancas_nao_registra(self):
        produto = Produto.objects.create(loja=self.loja, nome="Pão", preco_venda=Decimal('10'))
        atualizar_produto(produto, storage=StorageFalso(), usuario=self.usuario)
        self.assertFalse(RegistroDeAlteracao.objects.exists())
