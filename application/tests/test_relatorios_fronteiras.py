"""Fronteiras dos relatórios (achadas pelo teste de mutação): o dia exato em que um cliente muda de faixa,
o produto que fecha 80% da curva ABC, os centavos que ainda contam como dívida e os padrões das telas."""
from datetime import date, timedelta
from decimal import Decimal
from django.test import SimpleTestCase, TestCase
from application.relatorios.clientes import clientes_sumidos, idade_das_dividas, melhores_clientes
from application.relatorios.indicadores import Comparacao
from application.relatorios.pagamentos import recebido_por_forma
from application.relatorios.painel import montar_painel
from application.relatorios.produtos import curva_abc, lucro_estimado, previsao_de_reposicao, produtos_parados
from application.relatorios.selectors import montar_relatorio
from application.relatorios.vendas import mapa_de_horarios, vendido_x_recebido
from infrastructure.models import Unidade
from tests.apoio import CenarioDeLoja

AGORA = CenarioDeLoja.quando(2026, 3, 20, 15)  # sexta-feira
HOJE = AGORA.date()


def dias_atras(dias, hora=15):
    momento = AGORA - timedelta(days=dias)
    return momento.replace(hour=hora)


class DividasPorFaixaTest(TestCase):
    """Cliente que pagou há exatamente N dias: em que faixa ele cai."""

    def setUp(self):
        self.c = CenarioDeLoja()
        self.bolo = self.c.produto("Bolo", preco_venda='100')

    def devedor(self, nome, dias_sem_pagar, deve='10'):
        cliente = self.c.cliente(nome)
        self.c.venda(dias_atras(400), [(self.bolo, 1)], cliente=cliente)
        self.c.pagamento(cliente, str(Decimal('100') - Decimal(deve)), dias_atras(dias_sem_pagar))
        return cliente

    def test_cada_limite_fica_na_faixa_de_baixo(self):
        for dias in (0, 30, 31, 60, 61, 90, 91):
            self.devedor(f"{dias} dias", dias)
        dividas = idade_das_dividas(self.c.usuario(), agora=AGORA)
        self.assertEqual([(faixa.rotulo, faixa.clientes) for faixa in dividas.faixas], [
            ("Até 30 dias", 2), ("31 a 60 dias", 2), ("61 a 90 dias", 2), ("Mais de 90 dias", 1),
        ])
        self.assertEqual(dividas.devedores[-1].dias_sem_pagar, 0)  # pagou hoje: zero dias, não um
        self.assertEqual(dividas.acima_de(60), 3)  # 61, 90 e 91: exatamente 60 ainda não é "mais de 60"
        self.assertEqual(montar_painel(self.c.usuario(), agora=AGORA).indicadores.devendo_ha_muito_tempo, 3)

    def test_mesmo_tempo_sem_pagar_quem_deve_mais_vem_primeiro(self):
        self.devedor("Pouco", 40, deve='5')
        self.devedor("Muito", 40, deve='50')
        dividas = idade_das_dividas(self.c.usuario(), agora=AGORA)
        self.assertEqual([d.cliente.nome for d in dividas.devedores], ["Muito", "Pouco"])

    def test_cinquenta_centavos_ainda_e_divida(self):
        centavos = self.devedor("Centavos", 5, deve='0.50')
        self.assertEqual([d.cliente for d in idade_das_dividas(self.c.usuario(), agora=AGORA).devedores], [centavos])
        self.assertEqual(montar_relatorio(self.c.usuario(), agora=AGORA).clientes_devendo, [centavos])


class RankingDeClientesTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.bolo = self.c.produto("Bolo", preco_venda='10')

    def test_os_10_melhores_no_periodo_sem_data_da_ultima_compra(self):
        for numero in range(11):
            self.c.venda(dias_atras(5), [(self.bolo, numero + 1)], cliente=self.c.cliente(f"Cliente {numero:02}"))
        ranking = melhores_clientes(self.c.usuario(), inicio=HOJE - timedelta(days=10), fim=HOJE)
        self.assertEqual(len(ranking), 10)
        self.assertEqual((ranking[0].cliente.nome, ranking[0].ultima_compra, ranking[0].dias_sem_comprar), ("Cliente 10", None, None))

    def test_periodo_corta_dos_dois_lados_e_centavos_contam(self):
        ana = self.c.cliente("Ana")
        self.c.venda(dias_atras(20), [(self.bolo, 5)], cliente=ana)                 # antes do início
        self.c.venda(dias_atras(5), [(self.bolo, 1, '0.50')], cliente=ana)          # no período
        self.c.venda(AGORA + timedelta(days=5), [(self.bolo, 5)], cliente=ana)     # depois do fim
        [ranking] = melhores_clientes(self.c.usuario(), inicio=HOJE - timedelta(days=10), fim=HOJE)
        self.assertEqual((ranking.total, ranking.compras), (Decimal('0.50'), 1))

    def test_sumido_e_quem_nao_compra_ha_mais_de_60_dias_e_a_lista_para_em_20(self):
        self.c.venda(dias_atras(60, hora=12), [(self.bolo, 1)], cliente=self.c.cliente("Há 60 dias"))
        for numero in range(21):
            self.c.venda(dias_atras(61, hora=12), [(self.bolo, 1)], cliente=self.c.cliente(f"Sumido {numero:02}"))
        sumidos = clientes_sumidos(self.c.usuario(), agora=AGORA)
        self.assertEqual(len(sumidos), 20)
        self.assertNotIn("Há 60 dias", [s.cliente.nome for s in sumidos])


class PagamentosEProdutosTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()

    def test_balcao_sem_forma_de_pagamento(self):
        self.c.venda(AGORA, [(self.c.produto("Bolo"), 1)])
        linhas, _ = recebido_por_forma(self.c.usuario())
        self.assertEqual([linha.forma for linha in linhas], ["Não informada"])

    def test_linha_de_total_do_lucro(self):
        self.c.venda(AGORA, [(self.c.produto("Bolo", preco_venda='30', preco_custo='10'), 1)])
        total = lucro_estimado(self.c.usuario()).total
        self.assertEqual((total.nome, total.lucro, total.sem_custo), ("Total", Decimal('20.00'), False))

    def test_quem_cruza_80_e_95_por_cento_fica_na_classe_de_cima(self):
        for nome, valor in (("A", '80'), ("B", '15'), ("C", '5')):
            self.c.venda(AGORA, [(self.c.produto(nome, preco_venda=valor), 1)])
        linhas, _ = curva_abc(self.c.usuario())
        self.assertEqual([(linha.nome, linha.classe) for linha in linhas], [("A", "A"), ("B", "B"), ("C", "C")])

    def test_meio_quilo_parado_aparece(self):
        self.c.produto("Queijo", estoque=Decimal('0.5'), unidade=Unidade.QUILO)
        self.assertEqual([p.nome for p in produtos_parados(self.c.usuario(), dias=30, agora=AGORA)], ["Queijo"])


class ReposicaoTest(TestCase):
    """Padrão da tela: média dos últimos 30 dias, avisa o que acaba em até 14 dias."""

    def setUp(self):
        self.c = CenarioDeLoja()

    def previsao(self):
        return {p.nome: p for p in previsao_de_reposicao(self.c.usuario(), agora=AGORA)}

    def test_janela_comeca_29_dias_atras(self):
        bolo = self.c.produto("Bolo", estoque=1)
        self.c.venda(dias_atras(29), [(bolo, 3)])
        self.c.venda(dias_atras(30), [(bolo, 30)])  # fora da janela
        previsto = self.previsao()["Bolo"]
        self.assertEqual((previsto.media_diaria, previsto.dias_restantes, previsto.sugestao_de_compra), (Decimal('0.1'), 10, 1))

    def test_acaba_em_exatamente_14_dias_entra_e_sem_nada_a_comprar(self):
        for nome, estoque in (("Quatorze", 14), ("Quinze", 15)):
            produto = self.c.produto(nome, estoque=estoque)
            self.c.venda(dias_atras(1), [(produto, 30)])  # 1 por dia
        previsao = self.previsao()
        self.assertEqual(list(previsao), ["Quatorze"])
        self.assertEqual(previsao["Quatorze"].sugestao_de_compra, 0)

    def test_venda_de_meio_quilo_ja_conta(self):
        queijo = self.c.produto("Queijo", preco_venda='10', estoque=Decimal('0.001'), unidade=Unidade.QUILO)
        self.c.venda(dias_atras(1), [(queijo, Decimal('0.5'))])
        self.assertIn("Queijo", self.previsao())


class IndicadoresEGraficosTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.bolo = self.c.produto("Bolo", preco_venda='10')

    def test_mes_comeca_no_dia_1_e_semana_anterior_nao_pega_o_dia_de_antes(self):
        self.c.venda(CenarioDeLoja.quando(2026, 3, 1, 9), [(self.bolo, 1)])
        self.c.venda(CenarioDeLoja.quando(2026, 3, 6, 12), [(self.bolo, 1)])  # 14 dias antes: fora dos 7 anteriores
        indicadores = montar_painel(self.c.usuario(), agora=AGORA).indicadores
        self.assertEqual((indicadores.mes.atual, indicadores.sete_dias.anterior), (Decimal('20.00'), Decimal('0.00')))

    def test_recebido_no_primeiro_mes_do_grafico_conta(self):
        cliente = self.c.cliente("Ana")
        self.c.pagamento(cliente, '10', CenarioDeLoja.quando(2026, 1, 10))
        fluxo = vendido_x_recebido(self.c.usuario(), meses=3, agora=AGORA)
        self.assertEqual((fluxo[0].mes, fluxo[0].recebido), (date(2026, 1, 1), Decimal("10.00")))

    def test_mapa_pega_os_ultimos_90_dias(self):
        self.c.venda(dias_atras(89), [(self.bolo, 1)])
        self.c.venda(dias_atras(90), [(self.bolo, 5)])
        mapa = mapa_de_horarios(self.c.usuario(), agora=AGORA)
        self.assertEqual((mapa.melhor.total, mapa.melhor.vendas), (Decimal('10.00'), 1))

    def test_mapa_sem_vendas_fica_todo_apagado(self):
        mapa = mapa_de_horarios(self.c.usuario(), agora=AGORA)
        self.assertEqual({celula.intensidade for _, linha in mapa.linhas for celula in linha}, {0.0})


class ComparacaoTest(SimpleTestCase):

    def test_variacao_percentual(self):
        self.assertEqual(Comparacao(Decimal('110'), Decimal('40')).variacao, 175)

    def test_igual_ao_anterior_nao_e_queda(self):
        self.assertTrue(Comparacao(Decimal('100'), Decimal('100')).subiu)
