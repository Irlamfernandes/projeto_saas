from datetime import timedelta
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from tests.apoio import CenarioDeLoja


class PaginasDeRelatoriosTest(TestCase):

    def setUp(self):
        self.c = CenarioDeLoja()
        self.user = get_user_model().objects.create_user(username="op", password="x", loja=self.c.loja, deve_trocar_senha=False)
        self.client.force_login(self.user)

    def test_paginas_vazias_mostram_orientacao(self):
        casos = {
            'relatorios_vendas': "Nenhuma venda nesse período",
            'relatorios_produtos': "Nada para repor nos próximos 14 dias",
            'relatorios_clientes': "Ninguém devendo",
        }
        for rota, texto in casos.items():
            with self.subTest(rota):
                response = self.client.get(reverse(rota))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, texto)
                self.assertContains(response, 'aria-current="page">')

    def test_paginas_com_dados(self):
        bolo = self.c.produto("Bolo de cenoura", preco_venda='30', preco_custo='18', estoque=1)
        cliente = self.c.cliente("Ana")
        ontem = timezone.now() - timedelta(days=1)
        for _ in range(5):
            self.c.venda(ontem, [(bolo, 2)], cliente=cliente)

        vendas = self.client.get(reverse('relatorios_vendas'), {'dias': 90})
        produtos = self.client.get(reverse('relatorios_produtos'), {'parado': 30})
        clientes = self.client.get(reverse('relatorios_clientes'))

        self.assertEqual(vendas.context['dias'], 90)
        self.assertEqual(vendas.context['mais_vendidos'][0].quantidade, 10)
        self.assertContains(vendas, 'data-grafico="linha"')
        self.assertEqual(produtos.context['lucro'].total.lucro, Decimal('120.00'))
        self.assertEqual(produtos.context['reposicao'][0].nome, "Bolo de cenoura")
        self.assertEqual(produtos.context['dias_parado'], 30)
        self.assertContains(produtos, 'name="parado" value="30"')
        self.assertEqual(clientes.context['dividas'].total, Decimal('300.00'))
        self.assertEqual(clientes.context['melhores'][0].cliente, cliente)
        self.assertContains(clientes, 'id="dados-fluxo"')

    def test_periodo_padrao_e_ultimos_30_dias(self):
        response = self.client.get(reverse('relatorios_vendas'))
        self.assertEqual((response.context['data_fim'] - response.context['data_inicio']).days, 29)

    def test_exige_loja(self):
        self.client.logout()
        for rota in ('relatorios_vendas', 'relatorios_produtos', 'relatorios_clientes'):
            with self.subTest(rota):
                self.assertEqual(self.client.get(reverse(rota)).status_code, 302)


class FormasDePagamentoEAlteracoesTest(TestCase):

    def setUp(self):
        from application.vendas.services import registrar_venda
        self.c = CenarioDeLoja()
        self.user = get_user_model().objects.create_user(username="op", password="x", loja=self.c.loja, deve_trocar_senha=False)
        self.client.force_login(self.user)
        pao = self.c.produto("Pão", preco_venda='10', estoque=10)
        registrar_venda(itens=[(pao.pk, 2)], loja=self.c.loja, forma_pagamento='pix', usuario=self.user)

    def test_relatorio_de_vendas_mostra_o_recebido_por_forma(self):
        response = self.client.get(reverse('relatorios_vendas'))

        self.assertEqual(response.context['total_recebido'], Decimal('20.00'))
        self.assertEqual([f.forma for f in response.context['formas_de_pagamento']], ['Pix'])
        self.assertContains(response, "Formas de pagamento")

    def test_aba_de_alteracoes_lista_e_filtra(self):
        response = self.client.get(reverse('relatorios_alteracoes'))

        self.assertContains(response, "Venda registrada")
        self.assertContains(response, 'aria-current="page">Alterações')
        self.assertContains(response, "Balcão · 2× Pão (R$ 10,00) · total R$ 20,00 · Pix")

        filtrado = self.client.get(reverse('relatorios_alteracoes'), {'acao': 'venda_cancelada'})
        self.assertContains(filtrado, "Nenhuma alteração registrada ainda")

    def test_acao_desconhecida_no_filtro_mostra_tudo(self):
        response = self.client.get(reverse('relatorios_alteracoes'), {'acao': 'invalida'})
        self.assertEqual(response.context['acao'], '')
        self.assertEqual(len(response.context['registros']), 1)
