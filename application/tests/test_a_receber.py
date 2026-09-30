from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from application.a_receber.selectors import clientes_a_cobrar, cobranca_do_cliente
from application.a_receber.services import registrar_lembrete
from application.vendas.pendencias import Situacao
from infrastructure.models import (
    Acao, Cliente, ItemVenda, LembreteDePagamento, LojaModel, PagamentoCliente, Parcela, Produto, RegistroDeAlteracao, Venda,
)

HOJE = timezone.localdate()


class ACobrarTestCase(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.usuario = SimpleNamespace(is_superuser=False, loja=self.loja)

    def cliente(self, nome):
        return Cliente.objects.create(loja=self.loja, nome=nome)

    def venda(self, cliente, total, vencimento=None, dias_atras=1):
        venda = Venda.objects.create(loja=cliente.loja, cliente=cliente, valor_total=Decimal(total),
                                     data_venda=timezone.now() - timedelta(days=dias_atras))
        if vencimento:
            Parcela.objects.create(venda=venda, vencimento=vencimento)
        return venda

    def nomes(self, **kwargs):
        return [item.cliente.nome for item in clientes_a_cobrar(self.usuario, HOJE, **kwargs)]


class ClientesACobrarTest(ACobrarTestCase):

    def test_entram_atrasadas_as_de_hoje_e_as_dos_proximos_7_dias_em_ordem_de_vencimento(self):
        self.venda(self.cliente("Semana"), '10', HOJE + timedelta(days=7))
        self.venda(self.cliente("Hoje"), '10', HOJE)
        self.venda(self.cliente("Atrasada"), '10', HOJE - timedelta(days=3))
        self.venda(self.cliente("Longe"), '10', HOJE + timedelta(days=8))
        self.venda(self.cliente("Sem prazo"), '10')

        self.assertEqual(self.nomes(), ["Atrasada", "Hoje", "Semana"])

    def test_quem_ja_pagou_nao_entra(self):
        ana = self.cliente("Ana")
        self.venda(ana, '10', HOJE)
        PagamentoCliente.objects.create(loja=self.loja, cliente=ana, valor=Decimal('10'))
        self.assertEqual(self.nomes(), [])

    def test_o_pagamento_quita_a_mais_antiga_e_so_o_que_falta_entra(self):
        ana = self.cliente("Ana")
        self.venda(ana, '30', HOJE - timedelta(days=5), dias_atras=10)
        self.venda(ana, '20', HOJE + timedelta(days=2), dias_atras=5)
        self.venda(ana, '99', dias_atras=1)  # sem prazo: não entra no total
        PagamentoCliente.objects.create(loja=self.loja, cliente=ana, valor=Decimal('35'))

        [cobranca] = clientes_a_cobrar(self.usuario, HOJE)

        self.assertEqual(cobranca.total, Decimal('15.00'))
        self.assertEqual(cobranca.atrasado, Decimal('0.00'))
        self.assertEqual(cobranca.situacao, Situacao.A_VENCER)
        self.assertEqual(cobranca.primeiro_vencimento, HOJE + timedelta(days=2))

    def test_situacao_e_a_mais_grave(self):
        ana = self.cliente("Ana")
        self.venda(ana, '30', HOJE, dias_atras=10)
        self.venda(ana, '20', HOJE - timedelta(days=1), dias_atras=5)

        [cobranca] = clientes_a_cobrar(self.usuario, HOJE)

        self.assertEqual(cobranca.situacao, Situacao.ATRASADA)
        self.assertEqual((cobranca.atrasado, cobranca.total), (Decimal('20.00'), Decimal('50.00')))

    def test_vence_hoje(self):
        self.venda(self.cliente("Ana"), '30', HOJE)
        self.assertEqual(clientes_a_cobrar(self.usuario, HOJE)[0].situacao, Situacao.VENCE_HOJE)

    def test_marca_quem_ja_foi_lembrado_hoje(self):
        ana, bia = self.cliente("Ana"), self.cliente("Bia")
        self.venda(ana, '10', HOJE)
        self.venda(bia, '10', HOJE)
        LembreteDePagamento.objects.create(loja=self.loja, cliente=ana, valor=Decimal('10'))
        LembreteDePagamento.objects.create(loja=self.loja, cliente=bia, valor=Decimal('10'),
                                           enviado_em=timezone.now() - timedelta(days=1))

        lembrados = {item.cliente.nome: item.lembrado_hoje for item in clientes_a_cobrar(self.usuario, HOJE)}

        self.assertEqual(lembrados, {"Ana": True, "Bia": False})

    def test_so_a_loja_do_usuario(self):
        outra = LojaModel.objects.create(nome_loja="Outra")
        self.venda(Cliente.objects.create(loja=outra, nome="De fora"), '10', HOJE)
        self.venda(self.cliente("Daqui"), '10', HOJE)

        self.assertEqual(self.nomes(), ["Daqui"])
        superusuario = SimpleNamespace(is_superuser=True, loja=None)
        self.assertEqual(len(clientes_a_cobrar(superusuario, HOJE)), 2)

    def test_numero_de_consultas_nao_cresce_com_os_clientes(self):
        def consultas():
            # clientes, lembretes e os prefetches (vendas, parcelas, pagos no ato, itens com produto, pagamentos)
            with self.assertNumQueries(7):
                clientes_a_cobrar(self.usuario, HOJE)

        venda = self.venda(self.cliente("Ana"), '10', HOJE)
        bolo = Produto.objects.create(loja=self.loja, nome="Bolo", preco_venda=Decimal('10'))
        ItemVenda.objects.create(venda=venda, produto=bolo, quantidade=1, preco_unitario=Decimal('10'))
        consultas()
        for numero in range(5):
            self.venda(self.cliente(f"Cliente {numero}"), '10', HOJE - timedelta(days=numero))
        consultas()


class CobrancaDoClienteTest(ACobrarTestCase):

    def test_sem_nada_vencendo_devolve_none(self):
        ana = self.cliente("Ana")
        self.venda(ana, '10', HOJE + timedelta(days=30))
        self.assertIsNone(cobranca_do_cliente(ana, HOJE))
        self.assertIsNotNone(cobranca_do_cliente(ana, HOJE, dias=30))


class RegistrarLembreteTest(TestCase):

    def test_guarda_o_lembrete_e_registra_no_historico(self):
        loja = LojaModel.objects.create(nome_loja="Loja")
        ana = Cliente.objects.create(loja=loja, nome="Ana")
        usuario = get_user_model().objects.create_user(username="u", password="x", loja=loja, deve_trocar_senha=False)

        lembrete = registrar_lembrete(ana, valor=Decimal('25.50'), usuario=usuario)

        self.assertEqual((lembrete.loja, lembrete.cliente, lembrete.usuario, lembrete.valor), (loja, ana, usuario, Decimal('25.50')))
        self.assertEqual(str(lembrete), f"Ana · {HOJE:%d/%m/%Y}")
        registro = RegistroDeAlteracao.objects.get()
        self.assertEqual((registro.acao, registro.descricao), (Acao.LEMBRETE_ENVIADO, "Ana · R$ 25,50"))

    def test_data_do_lembrete_no_horario_de_brasilia(self):
        lembrete = LembreteDePagamento(cliente=Cliente(nome="Ana"), enviado_em=datetime(2026, 9, 30, 0, 30, tzinfo=UTC))
        self.assertEqual(str(lembrete), "Ana · 29/09/2026")
