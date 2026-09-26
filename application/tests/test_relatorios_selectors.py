from datetime import date, datetime
from decimal import Decimal
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from django.test import TestCase
from django.utils import timezone
from application.relatorios.periodos import inicios_dos_periodos
from application.relatorios.selectors import (
    Relatorio, faturamento_por_periodo, filtrar_por_intervalo, montar_painel, montar_relatorio,
)
from infrastructure.models import Cliente, LojaModel, PagamentoCliente, Produto, Venda

SP = ZoneInfo('America/Sao_Paulo')


def _local(ano, mes, dia, hora=12, minuto=0):
    return datetime(ano, mes, dia, hora, minuto, tzinfo=SP)


class PeriodosTest(TestCase):

    def test_hoje_comeca_a_meia_noite_local_mesmo_a_noite(self):
        """Regressão: às 22h de Brasília 'hoje' começava às 21h (meia-noite UTC)."""
        agora_utc = _local(2026, 9, 26, 22).astimezone(ZoneInfo('UTC'))

        inicios = inicios_dos_periodos(agora_utc)

        self.assertEqual(inicios['hoje'], _local(2026, 9, 26, 0))
        self.assertEqual(inicios['semana'], _local(2026, 9, 20, 0))
        self.assertEqual(inicios['quinzena'], _local(2026, 9, 12, 0))
        self.assertEqual(inicios['mes'], _local(2026, 9, 1, 0))
        self.assertEqual(inicios['bimestre'], _local(2026, 7, 29, 0))
        self.assertEqual(inicios['trimestre'], _local(2026, 6, 29, 0))
        self.assertEqual(inicios['ano'], _local(2026, 1, 1, 0))


class FaturamentoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        for dia, hora, valor in [(1, 12, '10.00'), (10, 12, '20.00'), (10, 23, '5.00'), (11, 0, '7.00')]:
            Venda.objects.create(loja=self.loja, valor_total=Decimal(valor), data_venda=_local(2026, 3, dia, hora))
        self.vendas = Venda.objects.all()

    def test_somas_por_periodo_numa_unica_consulta(self):
        with self.assertNumQueries(1):
            somas = faturamento_por_periodo(self.vendas, {'desde_dia_10': _local(2026, 3, 10, 0)})
        self.assertEqual(somas, {'total': Decimal('42.00'), 'desde_dia_10': Decimal('32.00')})

    def test_sem_vendas_soma_zero(self):
        somas = faturamento_por_periodo(Venda.objects.none(), {'hoje': _local(2026, 3, 1)})
        self.assertEqual(somas, {'total': Decimal('0.00'), 'hoje': Decimal('0.00')})

    def test_intervalo_usa_o_calendario_local(self):
        """A venda das 23h do dia 10 (02h UTC do dia 11) pertence ao dia 10."""
        dia_10 = filtrar_por_intervalo(self.vendas, date(2026, 3, 10), date(2026, 3, 10))
        self.assertEqual(sorted(v.valor_total for v in dia_10), [Decimal('5.00'), Decimal('20.00')])

    def test_intervalo_aberto(self):
        self.assertEqual(filtrar_por_intervalo(self.vendas).count(), 4)
        self.assertEqual(filtrar_por_intervalo(self.vendas, inicio=date(2026, 3, 11)).count(), 1)
        self.assertEqual(filtrar_por_intervalo(self.vendas, fim=date(2026, 3, 1)).count(), 1)


class MontarRelatorioTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        outra = LojaModel.objects.create(nome_loja="Loja B")
        self.usuario = SimpleNamespace(is_superuser=False, loja=self.loja)
        self.agora = _local(2026, 3, 20, 15)

        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        self.bia = Cliente.objects.create(loja=self.loja, nome="Bia")
        self.caio = Cliente.objects.create(loja=self.loja, nome="Caio")
        Cliente.objects.create(loja=self.loja, nome="Zerado")
        self._venda(self.ana, '100.00', _local(2026, 3, 20, 9))
        self._venda(self.bia, '300.00', _local(2026, 1, 5))
        PagamentoCliente.objects.create(loja=self.loja, cliente=self.caio, valor=Decimal('40.00'))
        self.arroz = Produto.objects.create(loja=self.loja, nome="Arroz", preco_venda=Decimal('5'), quantidade_estoque=9)
        self.feijao = Produto.objects.create(loja=self.loja, nome="Feijão", preco_venda=Decimal('8'), quantidade_estoque=1)

        cliente_b = Cliente.objects.create(loja=outra, nome="De Outra Loja")
        Venda.objects.create(loja=outra, cliente=cliente_b, valor_total=Decimal('999.00'), data_venda=self.agora)
        Produto.objects.create(loja=outra, nome="Milho", preco_venda=Decimal('1'))

    def _venda(self, cliente, valor, data):
        Venda.objects.create(loja=self.loja, cliente=cliente, valor_total=Decimal(valor), data_venda=data)

    def test_relatorio_completo_da_loja(self):
        relatorio = montar_relatorio(self.usuario, agora=self.agora)

        self.assertIsInstance(relatorio, Relatorio)
        self.assertEqual(relatorio.total_geral_vendas, Decimal('400.00'))
        self.assertEqual(relatorio.ticket_medio, Decimal('200.00'))
        self.assertEqual(relatorio.vendas_hoje_valor, Decimal('100.00'))
        self.assertEqual(relatorio.vendas_semana_valor, Decimal('100.00'))
        self.assertEqual(relatorio.vendas_mes_valor, Decimal('100.00'))
        self.assertEqual(relatorio.vendas_ano_valor, Decimal('400.00'))
        self.assertEqual([c.nome for c in relatorio.clientes_devendo], ["Bia", "Ana"])
        self.assertEqual(relatorio.total_fiado_pendente, Decimal('400.00'))
        self.assertEqual([(c.nome, c.valor_credito) for c in relatorio.clientes_credito], [("Caio", Decimal('40.00'))])
        self.assertEqual(relatorio.total_credito_clientes, Decimal('40.00'))
        self.assertEqual(relatorio.estoque_ordenado, [self.feijao, self.arroz])

    def test_intervalo_afeta_apenas_faturamento_e_ticket(self):
        relatorio = montar_relatorio(self.usuario, inicio=date(2026, 3, 1), agora=self.agora)

        self.assertEqual(relatorio.total_geral_vendas, Decimal('100.00'))
        self.assertEqual(relatorio.ticket_medio, Decimal('100.00'))
        self.assertEqual(relatorio.vendas_ano_valor, Decimal('400.00'))

    def test_superusuario_ve_todas_as_lojas(self):
        relatorio = montar_relatorio(SimpleNamespace(is_superuser=True, loja=None), agora=self.agora)
        self.assertEqual(relatorio.total_geral_vendas, Decimal('1399.00'))
        self.assertEqual(len(relatorio.estoque_ordenado), 3)

    def test_consultas_nao_crescem_com_o_numero_de_clientes(self):
        def consultas():
            with self.assertNumQueries(5) as contexto:
                montar_relatorio(self.usuario, agora=self.agora)
            return contexto

        consultas()
        for i in range(15):
            self._venda(Cliente.objects.create(loja=self.loja, nome=f"Novo {i}"), '1.00', self.agora)
        consultas()

    def test_como_contexto(self):
        contexto = montar_relatorio(self.usuario, agora=self.agora).como_contexto()
        self.assertEqual(contexto['total_geral_vendas'], Decimal('400.00'))
        self.assertEqual(len(contexto), 11)


class MontarPainelTest(TestCase):

    def test_painel_da_loja(self):
        loja = LojaModel.objects.create(nome_loja="Loja A")
        usuario = SimpleNamespace(is_superuser=False, loja=loja)
        agora = _local(2026, 3, 20, 15)
        Cliente.objects.create(loja=loja, nome="Ana")
        Venda.objects.create(loja=loja, valor_total=Decimal('10.00'), data_venda=_local(2026, 3, 20, 1))
        Venda.objects.create(loja=loja, valor_total=Decimal('20.00'), data_venda=_local(2026, 3, 10))
        Venda.objects.create(loja=loja, valor_total=Decimal('40.00'), data_venda=_local(2025, 12, 31))
        escasso = Produto.objects.create(loja=loja, nome="Escasso", preco_venda=Decimal('1'), quantidade_estoque=2)
        Produto.objects.create(loja=loja, nome="Farto", preco_venda=Decimal('1'), quantidade_estoque=50)

        painel = montar_painel(usuario, limite_estoque=5, agora=agora)

        self.assertEqual((painel.total_produtos, painel.total_clientes), (2, 1))
        self.assertEqual(painel.vendas_hoje, Decimal('10.00'))
        self.assertEqual(painel.vendas_quinzena, Decimal('30.00'))
        self.assertEqual(painel.vendas_ano, Decimal('30.00'))
        self.assertEqual(painel.total_geral, Decimal('70.00'))
        self.assertEqual(list(painel.produtos_baixo_estoque), [escasso])
        self.assertEqual(montar_painel(usuario, limite_estoque=100, agora=agora).produtos_baixo_estoque.count(), 2)
