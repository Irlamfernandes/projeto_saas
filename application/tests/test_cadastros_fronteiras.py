"""Fronteiras e detalhes de gastos, produtos, clientes e do histórico (achados pelo teste de mutação)."""
from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.test import SimpleTestCase, TestCase
from application.auditoria.services import registrar_alteracao
from application.clientes.exceptions import ClienteComSaldo, ClienteSemLoja, SenhaNaoConfere
from application.clientes.selectors import Movimento
from application.clientes.services import (
    apagar_dados_pessoais, atualizar_cliente, cadastrar_cliente, registrar_pagamento,
)
from application.gastos.exceptions import (
    CompraSemItens, EstoqueJaUsado, EstoqueNaoCobreAPerda, ProdutoDeOutraLoja, QuantidadeInvalidaParaUnidade,
)
from application.gastos.selectors import CATEGORIAS_SUGERIDAS, Mes, categorias_usadas, compras_do_mes
from application.gastos.services import (
    excluir_compra, excluir_despesa, excluir_perda, registrar_despesa, registrar_perda,
)
from application.produtos.exceptions import FalhaNoEnvioDeImagem, ImagemInvalida, LimiteDeFotosExcedido, ProdutoSemLoja
from application.produtos.selectors import filtrar_produtos
from application.produtos.services import cadastrar_produto
from application.tenancy import verificar_acesso_loja
from application.tests.test_gastos_services import DIA, GastosTestCase
from infrastructure.models import (
    Acao, Cliente, Compra, Despesa, LojaModel, PagamentoCliente, Perda, Produto, RegistroDeAlteracao, Unidade,
)
from infrastructure.utils.formatacao import reais
from tests.apoio import StorageFalso, imagem_de_teste

User = get_user_model()
FALHOU = RuntimeError("falhou no fim")


# ---------------------------------------------------------------- gastos

class GastosFronteirasTest(GastosTestCase):

    def test_compra_sem_fornecedor_nem_observacao(self):
        compra = self.comprar([(self.bolo.pk, Decimal('1'), Decimal('10'))])
        self.assertEqual((compra.fornecedor, compra.observacao), ('', ''))
        self.assertEqual(self.registro(Acao.COMPRA_REGISTRADA).descricao, f"Compra #{compra.pk} · {reais(Decimal('10'))}")

    def test_excluir_a_compra_quando_o_estoque_e_exatamente_o_comprado(self):
        self.bolo.quantidade_estoque = 0
        self.bolo.save()
        compra = self.comprar([(self.bolo.pk, Decimal('3'), Decimal('10'))], fornecedor="Atacadão")
        numero = compra.pk
        excluir_compra(compra, usuario=self.usuario)
        self.assertEqual(self.estoque(self.bolo), 0)
        excluida = self.registro(Acao.COMPRA_EXCLUIDA)
        self.assertEqual(excluida.descricao, f"Compra #{numero} · Atacadão · {reais(Decimal('30'))}")
        self.assertEqual(excluida.detalhes['data'], DIA.isoformat())

    def test_perda_de_todo_o_estoque_e_aceita_e_desfeita_com_a_data_no_historico(self):
        perda = registrar_perda(loja=self.loja, produto_id=self.bolo.pk, quantidade=Decimal('5'), data=DIA, motivo="Mofou")
        self.assertEqual(self.estoque(self.bolo), 0)
        excluir_perda(perda)
        self.assertEqual(self.registro(Acao.PERDA_EXCLUIDA).detalhes, {'data': DIA.isoformat()})

    def test_despesa_sem_descricao(self):
        despesa = registrar_despesa(loja=self.loja, data=DIA, categoria="Luz", valor=Decimal('50'))
        self.assertEqual(despesa.descricao, '')

    def test_compras_do_mes_trazem_os_itens_com_o_produto(self):
        self.comprar([(self.bolo.pk, Decimal('2'), Decimal('10')), (self.queijo.pk, Decimal('1.5'), Decimal('30'))])
        usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        with self.assertNumQueries(3):  # compras, itens, produtos
            nomes = sorted(item.produto.nome for compra in compras_do_mes(usuario, Mes.de(DIA)) for item in compra.itens.all())
        self.assertEqual(nomes, ["Bolo", "Queijo"])

    def test_categorias_sugeridas_quando_a_loja_ainda_nao_tem_despesas(self):
        usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        self.assertEqual(categorias_usadas(usuario), [
            'Água', 'Aluguel', 'Embalagens', 'Impostos', 'Internet e telefone', 'Luz', 'Manutenção', 'Propaganda',
            'Salários', 'Taxas e maquininha', 'Transporte',
        ])
        self.assertEqual(len(CATEGORIAS_SUGERIDAS), 11)


class GastosTudoOuNadaTest(GastosTestCase):
    """Se o último passo falhar, nada do que veio antes fica gravado."""

    def falhar_no_historico(self):
        return patch('application.gastos.services.registrar_alteracao', side_effect=FALHOU)

    def test_registrar_compra(self):
        with self.falhar_no_historico(), self.assertRaises(RuntimeError):
            self.comprar([(self.bolo.pk, Decimal('3'), Decimal('12'))])
        self.assertEqual((Compra.objects.count(), self.estoque(self.bolo)), (0, 5))

    def test_registrar_despesa(self):
        with self.falhar_no_historico(), self.assertRaises(RuntimeError):
            registrar_despesa(loja=self.loja, data=DIA, categoria="Luz", valor=Decimal('50'))
        self.assertFalse(Despesa.objects.exists())

    def test_registrar_perda(self):
        with self.falhar_no_historico(), self.assertRaises(RuntimeError):
            registrar_perda(loja=self.loja, produto_id=self.bolo.pk, quantidade=Decimal('2'), data=DIA, motivo="Caiu")
        self.assertEqual((Perda.objects.count(), self.estoque(self.bolo)), (0, 5))

    def test_excluir_compra(self):
        compra = self.comprar([(self.bolo.pk, Decimal('3'), Decimal('12'))])
        with patch.object(Compra, 'delete', side_effect=FALHOU), self.assertRaises(RuntimeError):
            excluir_compra(compra)
        self.assertEqual((self.estoque(self.bolo), RegistroDeAlteracao.objects.filter(acao=Acao.COMPRA_EXCLUIDA).count()), (8, 0))

    def test_excluir_despesa(self):
        despesa = registrar_despesa(loja=self.loja, data=DIA, categoria="Luz", valor=Decimal('50'))
        with patch.object(Despesa, 'delete', side_effect=FALHOU), self.assertRaises(RuntimeError):
            excluir_despesa(despesa)
        self.assertFalse(RegistroDeAlteracao.objects.filter(acao=Acao.DESPESA_EXCLUIDA).exists())

    def test_excluir_perda(self):
        perda = registrar_perda(loja=self.loja, produto_id=self.bolo.pk, quantidade=Decimal('2'), data=DIA, motivo="Caiu")
        with patch.object(Perda, 'delete', side_effect=FALHOU), self.assertRaises(RuntimeError):
            excluir_perda(perda)
        self.assertEqual(self.estoque(self.bolo), 3)


# ---------------------------------------------------------------- produtos

class ProdutosFronteirasTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")

    def test_estoque_baixo_vai_ate_5(self):
        for estoque in (5, 6):
            Produto.objects.create(loja=self.loja, nome=f"Com {estoque}", preco_venda=Decimal('1'), quantidade_estoque=estoque)
        baixos = filtrar_produtos(Produto.objects.all(), baixo_estoque=True)
        self.assertEqual([produto.nome for produto in baixos], ["Com 5"])

    def test_historico_do_cadastro_guarda_o_produto_e_as_fotos(self):
        produto = Produto(loja=self.loja, nome="Bolo", preco_venda=Decimal('30'))
        cadastrar_produto(produto, imagens=[imagem_de_teste()], storage=StorageFalso())
        detalhes = RegistroDeAlteracao.objects.get(acao=Acao.PRODUTO_CADASTRADO).detalhes
        self.assertEqual((detalhes['produto']['nome'], detalhes['fotos']), ("Bolo", 1))

    def test_falha_no_envio_fica_no_log_com_a_pasta(self):
        produto = Produto(loja=self.loja, nome="Bolo", preco_venda=Decimal('30'))
        with self.assertLogs('application.produtos.services', 'ERROR') as log, self.assertRaises(FalhaNoEnvioDeImagem):
            cadastrar_produto(produto, imagens=[imagem_de_teste()], storage=StorageFalso(falhar_no_envio=0))
        self.assertEqual(log.records[0].getMessage(), f"Falha ao enviar imagem do produto {produto.pk}")


# ---------------------------------------------------------------- clientes e histórico

class ClientesTudoOuNadaTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        self.dono = User.objects.create_user(username="dono", password="senha", loja=self.loja, deve_trocar_senha=False)
        historico = patch('application.clientes.services.registrar_alteracao', side_effect=FALHOU)
        historico.start()
        self.addCleanup(historico.stop)

    def test_cadastrar(self):
        with self.assertRaises(RuntimeError):
            cadastrar_cliente(Cliente(loja=self.loja, nome="Bia"))
        self.assertFalse(Cliente.objects.filter(nome="Bia").exists())

    def test_atualizar(self):
        self.ana.nome = "Ana Maria"
        with self.assertRaises(RuntimeError):
            atualizar_cliente(self.ana)
        self.assertEqual(Cliente.objects.get(pk=self.ana.pk).nome, "Ana")

    def test_registrar_pagamento(self):
        with self.assertRaises(RuntimeError):
            registrar_pagamento(self.ana, valor=Decimal('10'))
        self.assertFalse(PagamentoCliente.objects.exists())

    def test_apagar_dados(self):
        with self.assertRaises(RuntimeError):
            apagar_dados_pessoais(self.ana, usuario=self.dono, senha="senha")
        self.assertEqual(Cliente.objects.get(pk=self.ana.pk).nome, "Ana")


class ApagarDadosDoHistoricoTest(TestCase):
    """O histórico pode ter valores antigos que o cadastro não tem mais: todos somem."""

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.dono = User.objects.create_user(username="dono", password="senha", loja=self.loja, deve_trocar_senha=False)
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana", telefone="24999990000")

    def registrar(self, acao, descricao, detalhes=None):
        return registrar_alteracao(loja=self.loja, usuario=None, acao=acao, descricao=descricao, detalhes=detalhes,
                                   clientes=[self.ana])

    def apagar(self):
        apagar_dados_pessoais(self.ana, usuario=self.dono, senha="senha")
        return f"Cliente removido #{self.ana.pk}"

    def test_valores_da_foto_do_cadastro_e_das_edicoes(self):
        self.registrar(Acao.CLIENTE_CADASTRADO, "Antiga", {'cliente': {'nome': 'Antiga', 'telefone': '1111'}})
        self.registrar(Acao.CLIENTE_EDITADO, "Velha", {'alteracoes': {'nome': ['Velha', 'Ana'], 'email': ['v@x.com', '']}})
        pagamento = self.registrar(Acao.PAGAMENTO_REGISTRADO, "Antiga, Velha, 1111, v@x.com e 24999990000",
                                   {'observacao': 'ligar 1111'})
        anonimo = self.apagar()
        pagamento.refresh_from_db()
        self.assertEqual(pagamento.descricao, f"{anonimo}, {anonimo}, (removido), (removido) e (removido)")
        self.assertEqual(pagamento.detalhes, {'observacao': 'ligar (removido)'})

    def test_descricao_que_cresce_com_a_troca_e_cortada_no_tamanho_do_campo(self):
        registro = self.registrar(Acao.PAGAMENTO_REGISTRADO, "Ana " * 60)
        self.apagar()
        registro.refresh_from_db()
        self.assertEqual(len(registro.descricao), 255)

    def test_pagamento_guarda_a_observacao_no_historico(self):
        registrar_pagamento(self.ana, valor=Decimal('10'), observacao="Pix da filha")
        registro = RegistroDeAlteracao.objects.get(acao=Acao.PAGAMENTO_REGISTRADO)
        self.assertEqual(registro.detalhes, {'observacao': "Pix da filha"})


class RegistroDeAlteracaoTest(TestCase):

    def test_usuario_que_nao_entrou_nao_fica_no_registro(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        anonimo = SimpleNamespace(is_authenticated=False)
        registro = registrar_alteracao(loja=loja, usuario=anonimo, acao=Acao.CLIENTE_CADASTRADO, descricao="x")
        self.assertIsNone(registro.usuario)


class MovimentoTest(SimpleTestCase):

    def test_pagamento_sem_itens_nem_pendencias(self):
        movimento = Movimento(tipo='pagamento', data=datetime(2026, 9, 1), descricao="Pix", valor=Decimal('10'))
        self.assertEqual((movimento.itens, movimento.observacao, movimento.pendencias), ((), '', ()))


# ---------------------------------------------------------------- mensagens

class MensagensDosCadastrosTest(SimpleTestCase):
    """O texto é o que aparece na tela: confere palavra por palavra."""

    def test_mensagens(self):
        bolo = Produto(nome="Bolo", unidade=Unidade.UNIDADE)
        casos = {
            CompraSemItens(): "Adicione pelo menos um produto à compra.",
            ProdutoDeOutraLoja(): "Um dos produtos escolhidos não foi encontrado nesta loja.",
            QuantidadeInvalidaParaUnidade(bolo): "'Bolo' é contado por unidade: confira a quantidade.",
            EstoqueNaoCobreAPerda(bolo, "2 un."): "'Bolo' tem só 2 un. em estoque.",
            EstoqueJaUsado(bolo): (
                "Não dá para excluir: parte do 'Bolo' desta compra já foi vendida ou baixada. "
                "Acerte o estoque no cadastro do produto, se precisar."
            ),
            ProdutoSemLoja(): "Superusuários devem associar o produto a uma loja específica.",
            FalhaNoEnvioDeImagem(): "Não foi possível enviar as imagens agora. Nada foi salvo; tente novamente.",
            ImagemInvalida("foto.gif"): "Não foi possível ler a imagem 'foto.gif'. Envie uma foto JPG, PNG, WEBP ou HEIC.",
            LimiteDeFotosExcedido(5, 2): "Cada produto pode ter no máximo 5 fotos. Dá para adicionar mais 2.",
            LimiteDeFotosExcedido(5, 0): "Cada produto pode ter no máximo 5 fotos. Remova alguma antes de adicionar outra.",
            ClienteSemLoja(): "Superusuários devem associar o cliente a uma loja específica.",
            SenhaNaoConfere(): "Senha incorreta. Os dados do cliente não foram apagados.",
            ClienteComSaldo(Decimal('0.50')): (
                f"Este cliente ainda deve {reais(Decimal('0.50'))} na caderneta. Acerte o saldo antes de apagar os dados: "
                "a lei permite guardá-los enquanto houver valor a receber ou a devolver."
            ),
            ClienteComSaldo(Decimal('-0.50')): (
                f"Este cliente ainda tem {reais(Decimal('0.50'))} de crédito na caderneta. Acerte o saldo antes de apagar "
                "os dados: a lei permite guardá-los enquanto houver valor a receber ou a devolver."
            ),
        }
        for erro, mensagem in casos.items():
            with self.subTest(type(erro).__name__):
                self.assertEqual(str(erro), mensagem)

    def test_acesso_negado(self):
        casos = {
            "Acesso negado: Usuário não está vinculado a nenhuma loja.": SimpleNamespace(is_superuser=False, loja=None),
            "Acesso negado: esta loja está desativada.": SimpleNamespace(is_superuser=False, loja=LojaModel(ativo=False)),
        }
        for mensagem, usuario in casos.items():
            with self.subTest(mensagem), self.assertRaises(PermissionDenied) as erro:
                verificar_acesso_loja(usuario)
            self.assertEqual(str(erro.exception), mensagem)
