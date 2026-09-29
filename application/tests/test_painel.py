from decimal import Decimal
from types import SimpleNamespace
from django.test import TestCase
from application.relatorios.painel import montar_painel
from infrastructure.models import Cliente, LojaModel, Produto, Venda
from tests.apoio import CenarioDeLoja

AGORA = CenarioDeLoja.quando(2026, 3, 20, 15)  # sexta-feira
_local = CenarioDeLoja.quando


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
        Produto.objects.create(loja=loja, nome="Sob encomenda", preco_venda=Decimal('1'), controla_estoque=False)

        painel = montar_painel(usuario, limite_estoque=5, agora=agora)

        self.assertEqual((painel.total_produtos, painel.total_clientes), (3, 1))
        self.assertEqual(painel.vendas_hoje, Decimal('10.00'))
        self.assertEqual(painel.vendas_quinzena, Decimal('30.00'))
        self.assertEqual(painel.vendas_ano, Decimal('30.00'))
        self.assertEqual(painel.total_geral, Decimal('70.00'))
        self.assertEqual(list(painel.produtos_baixo_estoque), [escasso])
        self.assertEqual(montar_painel(usuario, limite_estoque=100, agora=agora).produtos_baixo_estoque.count(), 2)

    def test_uma_consulta_so_para_as_somas_das_vendas(self):
        c = CenarioDeLoja()
        c.venda(AGORA, [(c.produto("Bolo", preco_venda='10'), 1)])
        with self.assertNumQueries(4):  # somas das vendas, produtos, clientes, dívidas; o estoque baixo é lido no template
            montar_painel(c.usuario(), agora=AGORA)


class IndicadoresDoPainelTest(TestCase):

    def test_compara_com_o_periodo_anterior_ate_o_mesmo_horario(self):
        c = CenarioDeLoja()
        bolo = c.produto("Bolo", preco_venda='10')
        c.venda(CenarioDeLoja.quando(2026, 3, 20, 9), [(bolo, 12)])      # hoje
        c.venda(CenarioDeLoja.quando(2026, 3, 13, 10), [(bolo, 10)])     # sexta passada, antes das 15h
        c.venda(CenarioDeLoja.quando(2026, 3, 13, 18), [(bolo, 50)])     # sexta passada, depois das 15h: fora
        c.venda(CenarioDeLoja.quando(2026, 2, 5), [(bolo, 20)])          # fevereiro até dia 20
        cliente = c.cliente("Devedor antigo")
        c.venda(CenarioDeLoja.quando(2025, 12, 1), [(bolo, 3)], cliente=cliente)

        indicadores = montar_painel(c.usuario(), agora=AGORA).indicadores

        hoje = indicadores.hoje
        self.assertEqual((hoje.atual, hoje.anterior, hoje.variacao), (Decimal('120.00'), Decimal('100.00'), 20))
        self.assertEqual((indicadores.sete_dias.atual, indicadores.sete_dias.anterior), (Decimal('120.00'), Decimal('100.00')))
        self.assertEqual((indicadores.mes.atual, indicadores.mes.anterior), (Decimal('720.00'), Decimal('200.00')))
        self.assertEqual((indicadores.a_receber, indicadores.clientes_devendo, indicadores.devendo_ha_muito_tempo),
                         (Decimal('30.00'), 1, 1))
