from datetime import date
from decimal import Decimal
from django.test import TestCase
from application.gastos.selectors import (
    Mes, Resultado, categorias_usadas, compras_do_mes, despesas_do_mes, mes_escolhido, meses_para_escolher,
    perdas_do_mes, resultado_do_mes,
)
from infrastructure.models import Compra, Despesa, ItemCompra, LojaModel, Perda
from tests.apoio import CenarioDeLoja

HOJE = date(2026, 9, 27)
SETEMBRO = Mes.de(HOJE)


class MesTest(TestCase):

    def test_mes_de_uma_data_e_chave(self):
        self.assertEqual(Mes.de(date(2024, 2, 10)), Mes(date(2024, 2, 1), date(2024, 2, 29)))
        self.assertEqual(SETEMBRO.chave, '2026-09')

    def test_escolha_dos_ultimos_12_meses_com_o_atual_primeiro(self):
        meses = meses_para_escolher(HOJE)
        self.assertEqual((len(meses), meses[0].chave, meses[-1].chave), (12, '2026-09', '2025-10'))
        self.assertEqual(mes_escolhido('2026-03', HOJE).chave, '2026-03')
        for invalido in ('', '2020-01', 'lixo'):
            with self.subTest(invalido=invalido):
                self.assertEqual(mes_escolhido(invalido, HOJE), SETEMBRO)

    def test_contas_do_resultado(self):
        resultado = Resultado(vendas=Decimal('1000'), custo_do_vendido=Decimal('400'), despesas=Decimal('350'),
                              perdas=Decimal('50'), compras=Decimal('900'), itens_sem_custo=0)
        self.assertEqual((resultado.lucro_bruto, resultado.resultado), (Decimal('600'), Decimal('200')))


class GastosDoMesTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.usuario = self.c.usuario()
        self.loja = self.c.loja
        self.bolo = self.c.produto("Bolo", preco_venda='30', preco_custo='10', estoque=10)
        self.brinde = self.c.produto("Brinde", preco_venda='5', preco_custo='0', estoque=10)
        outra = LojaModel.objects.create(nome_loja="Outra")
        Despesa.objects.create(loja=outra, data=HOJE, categoria="Da outra", valor=Decimal('999'))

    def test_resultado_de_setembro(self):
        self.c.venda(CenarioDeLoja.quando(2026, 9, 5), [(self.bolo, 3)])                    # 90 vendidos, custo 30
        self.c.venda(CenarioDeLoja.quando(2026, 9, 6), [(self.brinde, 2)])                  # 10 vendidos, sem custo
        self.c.venda(CenarioDeLoja.quando(2026, 8, 31, 23), [(self.bolo, 10)])              # agosto: fora
        Despesa.objects.create(loja=self.loja, data=date(2026, 9, 1), categoria="Aluguel", valor=Decimal('50'))
        Despesa.objects.create(loja=self.loja, data=date(2026, 8, 31), categoria="Aluguel", valor=Decimal('999'))
        Perda.objects.create(loja=self.loja, data=date(2026, 9, 30), produto=self.bolo, quantidade=Decimal('0.5'),
                             custo_unitario=Decimal('10'), motivo="Quebrou")
        compra = Compra.objects.create(loja=self.loja, data=date(2026, 9, 2), valor_total=Decimal('200'))
        ItemCompra.objects.create(compra=compra, produto=self.bolo, quantidade=20, custo_unitario=Decimal('10'))

        resultado = resultado_do_mes(self.usuario, SETEMBRO)

        self.assertEqual(resultado, Resultado(
            vendas=Decimal('100.00'), custo_do_vendido=Decimal('30.00'), despesas=Decimal('50.00'),
            perdas=Decimal('5.00'), compras=Decimal('200.00'), itens_sem_custo=1,
        ))
        self.assertEqual(resultado.resultado, Decimal('15.00'))
        self.assertEqual([str(compra), str(compra.itens.get())], [f"Compra #{compra.pk} · 02/09/2026", "20× Bolo"])

    def test_mes_vazio_da_zero(self):
        vazio = resultado_do_mes(self.usuario, SETEMBRO)
        self.assertEqual((vazio.vendas, vazio.resultado, vazio.itens_sem_custo), (Decimal('0.00'), Decimal('0.00'), 0))

    def test_listas_do_mes_so_da_loja(self):
        despesa = Despesa.objects.create(loja=self.loja, data=HOJE, categoria="Luz", valor=Decimal('10'))
        Despesa.objects.create(loja=self.loja, data=date(2026, 10, 1), categoria="Luz", valor=Decimal('10'))

        self.assertEqual(list(despesas_do_mes(self.usuario, SETEMBRO)), [despesa])
        self.assertEqual(str(despesa), "Luz · 27/09/2026")
        self.assertEqual(list(compras_do_mes(self.usuario, SETEMBRO)), [])
        self.assertEqual(list(perdas_do_mes(self.usuario, SETEMBRO)), [])

    def test_categorias_sugeridas_mais_as_da_loja_em_ordem(self):
        Despesa.objects.create(loja=self.loja, data=HOJE, categoria="Gás", valor=Decimal('10'))
        categorias = categorias_usadas(self.usuario)
        self.assertIn("Gás", categorias)
        self.assertIn("Aluguel", categorias)
        self.assertNotIn("Da outra", categorias)
        self.assertEqual(categorias, sorted(categorias, key=str.casefold))
