from datetime import date, timedelta
from decimal import Decimal
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from application.vendas.pendencias import Pendencia, Situacao, abater, dividir, pendencias_do_cliente
from infrastructure.models import Cliente, LojaModel, PagamentoCliente, Parcela, Venda

HOJE = date(2026, 9, 27)


def pendencia(pendente='10.00', vencimento=None, valor='10.00'):
    return Pendencia(venda=None, vencimento=vencimento, valor=Decimal(valor), pendente=Decimal(pendente))


class SituacaoTest(SimpleTestCase):

    def test_cada_situacao(self):
        casos = {
            Situacao.PAGA: pendencia(pendente='0', vencimento=HOJE - timedelta(days=5)),
            Situacao.SEM_PRAZO: pendencia(),
            Situacao.ATRASADA: pendencia(vencimento=HOJE - timedelta(days=1)),
            Situacao.VENCE_HOJE: pendencia(vencimento=HOJE),
            Situacao.A_VENCER: pendencia(vencimento=HOJE + timedelta(days=1)),
        }
        for esperada, caso in casos.items():
            with self.subTest(esperada):
                self.assertEqual(caso.situacao(HOJE), esperada)

    def test_sem_data_usa_o_dia_de_hoje(self):
        self.assertEqual(pendencia(vencimento=date(2000, 1, 1)).situacao(), Situacao.ATRASADA)


class DividirTest(SimpleTestCase):

    def test_divide_em_centavos_e_o_resto_vai_na_ultima(self):
        self.assertEqual(dividir(Decimal('100.00'), 3), [Decimal('33.33'), Decimal('33.33'), Decimal('33.34')])
        self.assertEqual(dividir(Decimal('50.00'), 1), [Decimal('50.00')])


class AbaterTest(SimpleTestCase):

    def test_quita_na_ordem_e_para_quando_acaba_o_credito(self):
        resultado = abater([pendencia(), pendencia(), pendencia()], Decimal('15.00'))
        self.assertEqual([p.pendente for p in resultado], [Decimal('0.00'), Decimal('5.00'), Decimal('10.00')])

    def test_credito_maior_que_a_divida_quita_tudo(self):
        self.assertEqual([p.pendente for p in abater([pendencia()], Decimal('99'))], [Decimal('0.00')])


class PendenciasDoClienteTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja")
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana")

    def venda(self, total, dias_atras, pago_no_ato=None, vencimentos=()):
        venda = Venda.objects.create(
            loja=self.loja, cliente=self.ana, valor_total=Decimal(total),
            data_venda=timezone.now() - timedelta(days=dias_atras),
        )
        if pago_no_ato:
            PagamentoCliente.objects.create(loja=self.loja, cliente=self.ana, venda=venda, valor=Decimal(pago_no_ato))
        for vencimento in vencimentos:
            Parcela.objects.create(venda=venda, vencimento=vencimento)
        return venda

    def pagar(self, valor):
        PagamentoCliente.objects.create(loja=self.loja, cliente=self.ana, valor=Decimal(valor))

    def resumo(self):
        return [(p.venda.pk, p.vencimento, p.valor, p.pendente) for p in pendencias_do_cliente(self.ana)]

    def test_pagamento_da_caderneta_quita_primeiro_a_compra_mais_antiga(self):
        nova = self.venda('30.00', dias_atras=1, vencimentos=[HOJE])
        antiga = self.venda('50.00', dias_atras=10)
        self.pagar('60.00')

        self.assertEqual(self.resumo(), [
            (antiga.pk, None, Decimal('50.00'), Decimal('0.00')),
            (nova.pk, HOJE, Decimal('30.00'), Decimal('20.00')),
        ])

    def test_pago_no_ato_fica_com_a_propria_venda(self):
        antiga = self.venda('50.00', dias_atras=10)
        nova = self.venda('30.00', dias_atras=1, pago_no_ato='10.00')

        self.assertEqual(self.resumo(), [
            (antiga.pk, None, Decimal('50.00'), Decimal('50.00')),
            (nova.pk, None, Decimal('20.00'), Decimal('20.00')),
        ])

    def test_venda_paga_por_completo_no_ato_nao_tem_pendencia(self):
        self.venda('30.00', dias_atras=1, pago_no_ato='30.00')
        self.assertEqual(self.resumo(), [])

    def test_o_que_passou_do_total_no_ato_vira_credito_para_as_outras(self):
        antiga = self.venda('50.00', dias_atras=10)
        self.venda('30.00', dias_atras=1, pago_no_ato='40.00')

        self.assertEqual(self.resumo(), [(antiga.pk, None, Decimal('50.00'), Decimal('40.00'))])

    def test_varias_parcelas_dividem_o_que_ficou_a_prazo(self):
        venda = self.venda('100.00', dias_atras=1, vencimentos=[HOJE + timedelta(days=30), HOJE])
        self.pagar('40.00')

        self.assertEqual(self.resumo(), [
            (venda.pk, HOJE, Decimal('50.00'), Decimal('10.00')),
            (venda.pk, HOJE + timedelta(days=30), Decimal('50.00'), Decimal('50.00')),
        ])
        primeira, segunda = pendencias_do_cliente(self.ana)
        self.assertEqual((primeira.numero, primeira.de, segunda.numero, segunda.parcelada), (1, 2, 2, True))

    def test_uma_data_so_nao_e_parcelada(self):
        self.venda('10.00', dias_atras=1, vencimentos=[HOJE])
        [pendencia] = pendencias_do_cliente(self.ana)
        self.assertEqual((pendencia.numero, pendencia.de, pendencia.parcelada), (1, 1, False))

    def test_soma_do_que_falta_bate_com_o_saldo_da_caderneta(self):
        self.venda('50.00', dias_atras=10, vencimentos=[HOJE])
        self.venda('30.00', dias_atras=5, pago_no_ato='5.00')
        self.venda('12.00', dias_atras=1, pago_no_ato='20.00')
        self.pagar('33.00')

        falta = sum(p.pendente for p in pendencias_do_cliente(self.ana))
        self.assertEqual(falta, self.ana.saldo_geral)
        self.assertEqual(falta, Decimal('34.00'))

    def test_outro_cliente_nao_interfere(self):
        bia = Cliente.objects.create(loja=self.loja, nome="Bia")
        PagamentoCliente.objects.create(loja=self.loja, cliente=bia, valor=Decimal('100'))
        self.venda('50.00', dias_atras=1)

        self.assertEqual(self.resumo()[0][3], Decimal('50.00'))
