from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from application.vendas.selectors import (
    buscar_produto, clientes_do_usuario, produtos_em_estoque_do_usuario, vendas_do_usuario,
)
from infrastructure.models import Cliente, LojaModel, Produto, Venda


def _criar_produto(loja, nome, codigo='', estoque=10):
    return Produto.objects.create(
        loja=loja, nome=nome, codigo_interno=codigo,
        preco_venda=Decimal('10.00'), quantidade_estoque=estoque,
    )


class BuscarProdutoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        self.coca_lata = _criar_produto(self.loja, "Coca Lata", codigo="CL01")
        self.coca_2l = _criar_produto(self.loja, "Coca 2L", codigo="C2L")

    def test_encontra_por_codigo_interno_sem_diferenciar_maiusculas(self):
        self.assertEqual(buscar_produto(self.loja, "cl01"), self.coca_lata)

    def test_encontra_por_nome_exato(self):
        self.assertEqual(buscar_produto(self.loja, "coca 2l"), self.coca_2l)

    def test_encontra_por_id(self):
        self.assertEqual(buscar_produto(self.loja, str(self.coca_2l.pk)), self.coca_2l)

    def test_ignora_espacos_nas_pontas(self):
        self.assertEqual(buscar_produto(self.loja, "  CL01  "), self.coca_lata)

    def test_texto_inexistente_retorna_none_sem_erro(self):
        """Regressão: texto não numérico quebrava a busca por pk com ValueError (HTTP 500)."""
        self.assertIsNone(buscar_produto(self.loja, "Fanta"))

    def test_nome_parcial_nao_escolhe_produto_arbitrario(self):
        self.assertIsNone(buscar_produto(self.loja, "Coca"))

    def test_termo_vazio_nao_casa_com_produto_sem_codigo(self):
        _criar_produto(self.loja, "Sem Código")
        self.assertIsNone(buscar_produto(self.loja, "   "))

    def test_codigo_interno_tem_prioridade_sobre_id(self):
        conflitante = _criar_produto(self.loja, "Pão", codigo=str(self.coca_lata.pk))
        self.assertEqual(buscar_produto(self.loja, str(self.coca_lata.pk)), conflitante)

    def test_nao_encontra_produto_de_outra_loja(self):
        _criar_produto(self.outra_loja, "Guaraná", codigo="GU01")
        self.assertIsNone(buscar_produto(self.loja, "GU01"))


class ConsultasPorUsuarioTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.outra_loja = LojaModel.objects.create(nome_loja="Loja B")
        self.usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        self.superusuario = SimpleNamespace(is_superuser=True, loja=None)

    def test_vendas_do_usuario_filtra_pela_loja_e_ordena_mais_recentes_primeiro(self):
        antiga = Venda.objects.create(loja=self.loja)
        recente = Venda.objects.create(loja=self.loja)
        Venda.objects.create(loja=self.outra_loja)

        self.assertEqual(list(vendas_do_usuario(self.usuario)), [recente, antiga])
        self.assertEqual(vendas_do_usuario(self.superusuario).count(), 3)

    def test_clientes_do_usuario_filtra_pela_loja_em_ordem_alfabetica(self):
        zeca = Cliente.objects.create(loja=self.loja, nome="Zeca")
        ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        Cliente.objects.create(loja=self.outra_loja, nome="Bia")

        self.assertEqual(list(clientes_do_usuario(self.usuario)), [ana, zeca])
        self.assertEqual(clientes_do_usuario(self.superusuario).count(), 3)

    def test_produtos_em_estoque_exclui_zerados_e_outras_lojas(self):
        com_estoque = _criar_produto(self.loja, "Arroz")
        _criar_produto(self.loja, "Feijão", estoque=0)
        _criar_produto(self.outra_loja, "Milho")

        self.assertEqual(list(produtos_em_estoque_do_usuario(self.usuario)), [com_estoque])
        self.assertEqual(produtos_em_estoque_do_usuario(self.superusuario).count(), 2)
