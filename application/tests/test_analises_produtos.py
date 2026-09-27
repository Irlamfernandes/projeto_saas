from datetime import date
from decimal import Decimal
from django.test import TestCase
from application.relatorios.produtos import (
    curva_abc, lucro_estimado, percentual, previsao_de_reposicao, produtos_parados,
)
from tests.apoio import CenarioDeLoja

AGORA = CenarioDeLoja.quando(2026, 3, 20, 15)


class LucroEstimadoTest(TestCase):

    def test_lucro_por_produto_e_categoria(self):
        c = CenarioDeLoja()
        bolo = c.produto("Bolo", preco_venda='30', preco_custo='18', categoria="Doces")
        sonho = c.produto("Sonho", preco_venda='6', preco_custo='2', categoria="Doces")
        cafe = c.produto("Café", preco_venda='5', preco_custo='0')
        c.venda(CenarioDeLoja.quando(2026, 3, 10), [(bolo, 2), (sonho, 10), (cafe, 4)])

        relatorio = lucro_estimado(c.usuario(), inicio=date(2026, 3, 1))

        self.assertEqual([(l.nome, l.receita, l.custo, l.lucro, l.margem) for l in relatorio.produtos], [
            ("Sonho", Decimal('60.00'), Decimal('20.00'), Decimal('40.00'), Decimal('66.7')),
            ("Bolo", Decimal('60.00'), Decimal('36.00'), Decimal('24.00'), Decimal('40.0')),
            ("Café", Decimal('20.00'), Decimal('0.00'), Decimal('20.00'), Decimal('100.0')),
        ])
        self.assertEqual([(l.nome, l.lucro) for l in relatorio.categorias], [("Doces", Decimal('64.00')), ("Sem categoria", Decimal('20.00'))])
        self.assertEqual((relatorio.total.receita, relatorio.total.lucro), (Decimal('140.00'), Decimal('84.00')))
        self.assertEqual(relatorio.produtos_sem_custo, 1)

    def test_sem_vendas(self):
        relatorio = lucro_estimado(CenarioDeLoja().usuario())
        self.assertEqual((relatorio.produtos, relatorio.total.lucro, relatorio.total.margem), ([], Decimal('0.00'), Decimal('0.00')))

    def test_percentual(self):
        self.assertEqual(percentual(1, 3), Decimal('33.3'))
        self.assertEqual(percentual(5, 0), Decimal('0.00'))


class CurvaABCTest(TestCase):

    def test_classifica_pelo_faturamento_acumulado(self):
        c = CenarioDeLoja()
        vendas = [("A1", 700), ("A2", 150), ("B1", 80), ("C1", 50), ("C2", 20)]
        c.venda(CenarioDeLoja.quando(2026, 3, 10), [(c.produto(nome, preco_venda=str(valor)), 1) for nome, valor in vendas])

        linhas, resumo = curva_abc(c.usuario())

        self.assertEqual([(l.nome, l.classe, l.participacao, l.acumulado) for l in linhas], [
            ("A1", "A", Decimal('70.0'), Decimal('70.0')),
            ("A2", "A", Decimal('15.0'), Decimal('85.0')),  # cruzou 80%: ainda A
            ("B1", "B", Decimal('8.0'), Decimal('93.0')),
            ("C1", "B", Decimal('5.0'), Decimal('98.0')),   # cruzou 95%: ainda B
            ("C2", "C", Decimal('2.0'), Decimal('100.0')),
        ])
        self.assertEqual([(r.classe, r.produtos, r.participacao) for r in resumo], [
            ("A", 2, Decimal('85.0')), ("B", 2, Decimal('13.0')), ("C", 1, Decimal('2.0')),
        ])

    def test_sem_vendas(self):
        linhas, resumo = curva_abc(CenarioDeLoja().usuario())
        self.assertEqual(linhas, [])
        self.assertEqual([r.produtos for r in resumo], [0, 0, 0])


class ProdutosParadosTest(TestCase):

    def test_lista_quem_nao_vende_ha_tempo_ou_nunca_vendeu(self):
        c = CenarioDeLoja()
        vende_sempre = c.produto("Pão", estoque=10)
        parado = c.produto("Forma de bolo", preco_custo='40', estoque=3)
        nunca = c.produto("Vela", preco_custo='2', estoque=5)
        c.produto("Sem estoque", estoque=0)
        c.produto("Sob encomenda", estoque=5, controla_estoque=False)
        c.venda(CenarioDeLoja.quando(2026, 3, 19), [(vende_sempre, 1)])
        c.venda(CenarioDeLoja.quando(2026, 1, 5), [(parado, 1)])

        parados = produtos_parados(c.usuario(), dias=60, agora=AGORA)

        self.assertEqual([(p.nome, p.dias_parado, p.valor_em_estoque) for p in parados], [
            ("Vela", None, Decimal('10.00')),
            ("Forma de bolo", 74, Decimal('120.00')),
        ])


class PrevisaoDeReposicaoTest(TestCase):

    def test_quem_acaba_dentro_do_horizonte_com_sugestao_de_compra(self):
        c = CenarioDeLoja()
        leite = c.produto("Leite", estoque=0)
        fermento = c.produto("Fermento", estoque=2)
        farinha = c.produto("Farinha", estoque=100)
        c.venda(CenarioDeLoja.quando(2026, 3, 10), [(leite, 30), (fermento, 30), (farinha, 30)])
        c.venda(CenarioDeLoja.quando(2026, 1, 1), [(farinha, 999)])  # fora da janela de 30 dias
        encomenda = c.produto("Bolo sob encomenda", estoque=0, controla_estoque=False)
        c.venda(CenarioDeLoja.quando(2026, 3, 10), [(encomenda, 30)])  # sem controle: nunca "acaba"

        previsao = previsao_de_reposicao(c.usuario(), janela=30, horizonte=14, agora=AGORA)

        self.assertEqual([(p.nome, p.media_diaria, p.dias_restantes, p.sugestao_de_compra) for p in previsao], [
            ("Leite", Decimal('1.0'), 0, 14),
            ("Fermento", Decimal('1.0'), 2, 12),
        ])

    def test_por_quilo_usa_fracoes_e_leva_a_unidade(self):
        c = CenarioDeLoja()
        queijo = c.produto("Queijo", estoque=Decimal('1.5'), unidade='kg')
        c.venda(CenarioDeLoja.quando(2026, 3, 10), [(queijo, Decimal('15'))])

        [previsao] = previsao_de_reposicao(c.usuario(), janela=30, horizonte=14, agora=AGORA)

        self.assertEqual((previsao.estoque, previsao.media_diaria, previsao.dias_restantes, previsao.sugestao_de_compra,
                          previsao.unidade), (Decimal('1.5'), Decimal('0.5'), 3, 6, 'kg'))
