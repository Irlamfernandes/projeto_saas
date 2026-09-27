import importlib
from decimal import Decimal
from django.apps import apps
from django.test import TestCase
from infrastructure.models import Cliente, LojaModel, PagamentoCliente, Venda

migracao = importlib.import_module('infrastructure.migrations.0011_liga_pagamentos_no_ato_as_vendas')


class LigaPagamentosNoAtoTest(TestCase):

    def setUp(self):
        self.loja = LojaModel.objects.create(nome_loja="Loja A")
        self.ana = Cliente.objects.create(loja=self.loja, nome="Ana")
        self.bia = Cliente.objects.create(loja=self.loja, nome="Bia")

    def _pagamento(self, cliente, observacao):
        return PagamentoCliente.objects.create(loja=self.loja, cliente=cliente, valor=Decimal('10'), observacao=observacao)

    def test_liga_o_pagamento_a_venda_do_mesmo_cliente(self):
        venda = Venda.objects.create(loja=self.loja, cliente=self.ana)
        pagamento = self._pagamento(self.ana, f"Pagamento no ato da Venda #{venda.pk}")

        migracao.ligar(apps, None)

        pagamento.refresh_from_db()
        self.assertEqual(pagamento.venda, venda)

    def test_nao_mexe_em_pagamento_que_ficou_com_outro_cliente(self):
        """Venda que já tinha mudado de cliente pelo bug antigo: dinheiro não se move sozinho."""
        venda = Venda.objects.create(loja=self.loja, cliente=self.bia)
        pagamento = self._pagamento(self.ana, f"Pagamento no ato da Venda #{venda.pk}")

        migracao.ligar(apps, None)

        pagamento.refresh_from_db()
        self.assertIsNone(pagamento.venda)
        self.assertEqual(pagamento.cliente, self.ana)

    def test_ignora_observacoes_parecidas_e_vendas_inexistentes(self):
        outros = [
            self._pagamento(self.ana, "Pagamento no ato da Venda #999999"),
            self._pagamento(self.ana, "Pagamento no ato da Venda #12 (parcial)"),
            self._pagamento(self.ana, "Pix"),
        ]
        migracao.ligar(apps, None)
        self.assertFalse(PagamentoCliente.objects.filter(pk__in=[p.pk for p in outros], venda__isnull=False).exists())
